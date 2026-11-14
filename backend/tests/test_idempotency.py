"""Idempotent consume: replay, conflicts, rollback, scoped keys and PG races."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, build_engine, get_db
from app.main import app
from app.models import Activity, ConsumeIdempotency, Snack, User
from app.security import hash_password


def key_headers(auth_header: dict, key: str) -> dict:
    return {**auth_header, "Idempotency-Key": key}


def test_retry_returns_same_payload_with_no_second_stock_or_audit(setup, auth):
    client, factory, ids = setup
    url = f"/snacks/{ids['snack']}/consume"
    headers = key_headers(auth['member'], 'test-retry-0001')
    first = client.post(url, headers=headers, json={'amount': 1})
    repeat = client.post(url, headers=headers, json={'amount': 1})
    assert first.status_code == repeat.status_code == 200
    assert first.json() == repeat.json()
    assert first.json()['quantity'] == 2
    with factory() as db:
        assert db.get(Snack, ids['snack']).quantity == 2
        assert len(db.scalars(select(Activity)).all()) == 1
        assert len(db.scalars(select(ConsumeIdempotency)).all()) == 1


def test_same_key_different_amount_or_snack_is_conflict(setup, auth):
    client, factory, ids = setup
    url = f"/snacks/{ids['snack']}/consume"
    headers = key_headers(auth['member'], 'test-unique-0002')
    assert client.post(url, headers=headers, json={'amount': 1}).status_code == 200
    for url_to_try, amount in ((url, 2), ('/snacks/99999/consume', 1)):
        response = client.post(url_to_try, headers=headers, json={'amount': amount})
        assert response.status_code == 409, response.text
        assert response.json()['error']['code'] == 'IDEMPOTENCY_KEY_REUSED'
    with factory() as db:
        assert db.get(Snack, ids['snack']).quantity == 2
        assert len(db.scalars(select(Activity)).all()) == 1


def test_same_key_is_scoped_to_each_user(setup, auth):
    client, factory, ids = setup
    url = f"/snacks/{ids['snack']}/consume"
    for role in ('member', 'admin'):
        response = client.post(url, headers=key_headers(auth[role], 'shared-key-0003'), json={'amount': 1})
        assert response.status_code == 200, response.text
    with factory() as db:
        assert db.get(Snack, ids['snack']).quantity == 1
        assert len(db.scalars(select(Activity)).all()) == 2
        assert len(db.scalars(select(ConsumeIdempotency)).all()) == 2


def test_invalid_key_is_rejected_before_stock_change(setup, auth):
    client, factory, ids = setup
    url = f"/snacks/{ids['snack']}/consume"
    for value in ('short', 'has whitespace', 'x'*129, '../not/valid'):
        response = client.post(url, headers=key_headers(auth['member'], value), json={'amount': 1})
        assert response.status_code == 422, response.text
        assert response.json()['error']['code'] == 'INVALID_IDEMPOTENCY_KEY'
    with factory() as db:
        assert db.get(Snack, ids['snack']).quantity == 3
        assert db.scalars(select(Activity)).all() == []
        assert db.scalars(select(ConsumeIdempotency)).all() == []


def test_audit_failure_rolls_back_stock_and_key_claim(setup, auth):
    client, factory, ids = setup
    url = f"/snacks/{ids['snack']}/consume"
    headers = key_headers(auth['member'], 'rollback-0004')

    def fail_audit(_mapper, _connection, _target):
        raise RuntimeError('Test audit insertion failure')

    event.listen(Activity, 'before_insert', fail_audit)
    try:
        result = client.post(url, headers=headers, json={'amount': 1})
        assert result.status_code == 500
    finally:
        event.remove(Activity, 'before_insert', fail_audit)
    with factory() as db:
        assert db.get(Snack, ids['snack']).quantity == 3
        assert db.scalars(select(Activity)).all() == []
        assert db.scalars(select(ConsumeIdempotency)).all() == []
    result = client.post(url, headers=headers, json={'amount': 1})
    assert result.status_code == 200
    with factory() as db:
        assert db.get(Snack, ids['snack']).quantity == 2
        assert len(db.scalars(select(Activity)).all()) == 1


def test_without_key_retains_backward_compatibility(setup, auth):
    client, factory, ids = setup
    url = f"/snacks/{ids['snack']}/consume"
    for _ in range(2):
        assert client.post(url, headers=auth['member'], json={'amount': 1}).status_code == 200
    with factory() as db:
        assert db.get(Snack, ids['snack']).quantity == 1
        assert db.scalars(select(ConsumeIdempotency)).all() == []


@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'), reason='Set TEST_POSTGRES_URL for actual PostgreSQL parallel-key test')
def test_ten_identical_keys_execute_only_once_in_postgresql():
    """Ten simultaneous HTTP retries all replay 200; only ONE stock decrement."""
    engine = build_engine(os.environ['TEST_POSTGRES_URL'])
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:12]
    with factory() as db:
        user = User(name='Idem Runner', email=f'idem-{suffix}@example.com',
                    password_hash=hash_password('Password123!'), role='member')
        snack = Snack(name=f'Idem Race {suffix}', category='savoury', quantity=3, low_stock_threshold=5)
        db.add_all([user, snack]); db.commit()
        user_id, snack_id = user.id, snack.id

    def test_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            login = client.post('/auth/login', json={'email': user.email, 'password': 'Password123!'})
            assert login.status_code == 200, login.text
            headers = {'Authorization': f"Bearer {login.json()['token']}",
                       'Idempotency-Key': f'postgres-retry-{suffix}'}
            barrier = Barrier(10)

            def worker(_):
                barrier.wait(timeout=20)
                response = client.post(f'/snacks/{snack_id}/consume',
                                       headers=headers, json={'amount': 1})
                return response.status_code, response.json()

            with ThreadPoolExecutor(max_workers=10) as executor:
                results = list(executor.map(worker, range(10)))
            assert Counter(status for status, _ in results) == Counter({200: 10}), results
            assert all(payload == results[0][1] for _, payload in results)
        with factory() as db:
            assert db.get(Snack, snack_id).quantity == 2
            assert len(db.scalars(select(Activity).where(Activity.snack_id == snack_id)).all()) == 1
            assert len(db.scalars(select(ConsumeIdempotency).where(
                ConsumeIdempotency.user_id == user_id)).all()) == 1
    finally:
        app.dependency_overrides.clear()
        with factory() as db:
            from sqlalchemy import delete
            from app.models import LoginSession, Vote
            db.execute(delete(ConsumeIdempotency).where(ConsumeIdempotency.user_id == user_id))
            db.execute(delete(Activity).where(Activity.snack_id == snack_id))
            db.execute(delete(Vote).where(Vote.snack_id == snack_id))
            db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))
            db.execute(delete(Snack).where(Snack.id == snack_id))
            db.execute(delete(User).where(User.id == user_id))
            db.commit()
        engine.dispose()


def test_retry_replays_even_after_snack_deleted(setup, auth):
    client, factory, ids = setup
    url = f"/snacks/{ids['snack']}/consume"
    headers = key_headers(auth['member'], 'after-delete-0005')
    response = client.post(url, headers=headers, json={'amount': 1})
    assert response.status_code == 200
    assert client.delete(f"/snacks/{ids['snack']}", headers=auth['admin']).status_code == 204
    replay = client.post(url, headers=headers, json={'amount': 1})
    assert replay.status_code == 200
    assert replay.json() == response.json()
    with factory() as db:
        assert len(db.scalars(select(Activity)).all()) == 1
        assert len(db.scalars(select(ConsumeIdempotency)).all()) == 1
