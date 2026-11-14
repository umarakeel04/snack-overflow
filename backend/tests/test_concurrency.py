"""Prove correctness under contention at the DATABASE layer, not via Python locks."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import os
import uuid
import pytest
from sqlalchemy import select, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from app.database import Base, build_engine
from app.models import Activity, Snack, User, Vote
from app.security import hash_password
from app.services import InventoryFailure, consume_stock


def contest(factory, snack_id: int, user_id: int, attempts: int = 10):
    barrier = Barrier(attempts)
    def worker(_):
        with factory() as db:
            barrier.wait(timeout=20)
            try:
                consume_stock(db, snack_id, user_id, 1)
                return 200
            except InventoryFailure as exc:
                db.rollback()
                return exc.status
    with ThreadPoolExecutor(max_workers=attempts) as executor:
        results = list(executor.map(worker, range(attempts)))
    with factory() as db:
        stock = db.get(Snack, snack_id).quantity
        audits = db.scalars(select(Activity).where(Activity.snack_id == snack_id)).all()
    return results, stock, audits


def test_ten_compete_for_last_three_sqlite(setup):
    _, factory, ids = setup
    codes, quantity, activities = contest(factory, ids['snack'], ids['member'])
    assert codes.count(200) == 3, codes
    assert codes.count(409) == 7, codes
    assert quantity == 0
    assert len(activities) == 3
    assert all(a.amount == 1 and a.action == 'consumed' for a in activities)


def test_activity_failure_rolls_back_stock(setup):
    _, factory, ids = setup
    def sabotage(_mapper, _connection, _target):
        raise RuntimeError('Simulated audit insert failure')
    event.listen(Activity, 'before_insert', sabotage)
    try:
        with factory() as db:
            with pytest.raises(RuntimeError, match='audit insert'):
                consume_stock(db, ids['snack'], ids['member'], 2)
            db.rollback()
    finally:
        event.remove(Activity, 'before_insert', sabotage)
    with factory() as db:
        assert db.get(Snack, ids['snack']).quantity == 3
        assert db.scalars(select(Activity)).all() == []


@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'), reason='Set TEST_POSTGRES_URL to run PostgreSQL contention test')
def test_postgres_concurrency_and_one_vote_per_user():
    """Executed in GitHub CI against actual Postgres, not a mock or SQLite."""
    engine = build_engine(os.environ['TEST_POSTGRES_URL'])
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:12]
    with factory() as db:
        user = User(name='Test Runner', email=f'runner-{suffix}@test.dev', password_hash=hash_password('test-password'), role='member')
        snack = Snack(name=f'Concurrency Test {suffix}', category='savoury', quantity=3, low_stock_threshold=5)
        db.add_all([user, snack])
        db.commit()
        uid, sid = user.id, snack.id
    try:
        codes, quantity, audits = contest(factory, sid, uid)
        assert codes.count(200) == 3, codes
        assert codes.count(409) == 7, codes
        assert quantity == 0 and len(audits) == 3

        barrier = Barrier(10)
        def vote_worker(_):
            with factory() as db:
                barrier.wait(timeout=20)
                db.add(Vote(user_id=uid, snack_id=sid))
                try:
                    db.commit()
                    return 201
                except IntegrityError:
                    db.rollback()
                    return 409
        with ThreadPoolExecutor(max_workers=10) as pool:
            votes = list(pool.map(vote_worker, range(10)))
        assert votes.count(201) == 1, votes
        assert votes.count(409) == 9, votes
        with factory() as db:
            assert len(db.scalars(select(Vote).where(Vote.user_id == uid, Vote.snack_id == sid)).all()) == 1
    finally:
        with factory() as db:
            db.query(Vote).filter(Vote.snack_id == sid).delete()
            db.query(Activity).filter(Activity.snack_id == sid).delete()
            db.query(Snack).filter(Snack.id == sid).delete()
            db.query(User).filter(User.id == uid).delete()
            db.commit()
        engine.dispose()
