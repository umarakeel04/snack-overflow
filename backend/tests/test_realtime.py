"""Authentication, event framing, and PostgreSQL post-commit invalidation."""
import json
import os
import uuid

import pytest
from sqlalchemy import delete, insert, update

from app.database import Base, build_engine
from app.models import Snack
from app.realtime import format_change_event, install_notification_triggers


def test_stream_requires_login(setup):
    client, _, _ = setup
    result = client.get('/snacks/events')
    assert result.status_code == 401
    assert result.json()['error']['code'] == 'UNAUTHORIZED'


@pytest.mark.skipif(os.getenv('DATABASE_URL', '').startswith('postgresql+'),
                    reason='Streaming endpoint would be live on PostgreSQL')
def test_stream_is_unavailable_without_postgres(setup, auth):
    client, _, _ = setup
    # The backend's isolated tests use SQLite; the production Docker stack
    # uses PostgreSQL LISTEN/NOTIFY for realtime changes.
    result = client.get('/snacks/events', headers=auth['member'])
    assert result.status_code == 503
    assert result.json()['error']['code'] == 'REALTIME_UNAVAILABLE'


def test_notification_payload_cannot_inject_extra_sse_frames():
    event = format_change_event('{"table": "snacks\\n\\nevent: malicious", "operation": "UPDATE"}')
    assert event.count('\n\n') == 1
    assert '\nevent: malicious' not in event
    assert event.startswith('event: change\ndata: ')
    assert json.loads(event.split('data: ', 1)[1])['operation'] == 'UPDATE'


def test_install_notification_triggers_is_safe_for_sqlite(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'trigger.db'}")
    install_notification_triggers(engine)
    engine.dispose()


@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'), reason='Needs PostgreSQL for LISTEN/NOTIFY')
def test_postgres_notifications_only_after_commit():
    import psycopg

    url = os.environ['TEST_POSTGRES_URL']
    engine = build_engine(url)
    Base.metadata.create_all(engine)
    # Running twice also verifies repeated app startup is safe.
    install_notification_triggers(engine)
    install_notification_triggers(engine)
    dsn = url.replace('postgresql+psycopg://', 'postgresql://', 1)
    name = 'Realtime Test ' + uuid.uuid4().hex[:12]
    snack_id = None
    try:
        with psycopg.connect(dsn, autocommit=True) as listener:
            listener.execute('LISTEN snack_overflow_changes')
            with engine.begin() as connection:
                snack_id = connection.scalar(insert(Snack).values(
                    name=name, category='sweet', quantity=3, low_stock_threshold=5
                ).returning(Snack.id))
            event = next(listener.notifies(timeout=3, stop_after=1), None)
            assert event is not None
            assert json.loads(event.payload)['table'] == 'snacks'
            # Rollback must not notify other connected tabs or change stock.
            with engine.connect() as connection:
                transaction = connection.begin()
                connection.execute(update(Snack).where(Snack.id == snack_id).values(quantity=2))
                transaction.rollback()
            assert next(listener.notifies(timeout=0.5, stop_after=1), None) is None
    finally:
        if snack_id is not None:
            with engine.begin() as connection:
                connection.execute(delete(Snack).where(Snack.id == snack_id))
        engine.dispose()
