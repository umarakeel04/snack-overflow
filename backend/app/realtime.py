"""PostgreSQL-backed invalidation events for the authenticated SSE pantry stream.

Only table names and operations are broadcast, not users or private data.
PostgreSQL delivers NOTIFY only after the mutation transaction commits;
rolled-back stock/vote changes generate no notifications.
"""
import json

from sqlalchemy.engine import Engine

CHANNEL = "snack_overflow_changes"


def install_notification_triggers(engine: Engine) -> None:
    """Idempotently install statement-level triggers on an existing PG database.

    SQLite-backed unit tests deliberately omit PostgreSQL-only realtime support.
    """
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE OR REPLACE FUNCTION snack_overflow_notify_change()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                PERFORM pg_notify(
                    'snack_overflow_changes',
                    json_build_object('table', TG_TABLE_NAME, 'operation', TG_OP)::text
                );
                RETURN NULL;
            END;
            $$;
        """)
        for table in ("snacks", "votes"):
            connection.exec_driver_sql(f"""
                CREATE OR REPLACE TRIGGER snack_overflow_change_notify
                AFTER INSERT OR UPDATE OR DELETE ON {table}
                FOR EACH STATEMENT EXECUTE FUNCTION snack_overflow_notify_change();
            """)


def format_change_event(payload: str) -> str:
    """Return a safe SSE event. Never allow notification text to forge extra frames."""
    try:
        parsed = json.loads(payload)
    except (ValueError, TypeError):
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    return f"event: change\ndata: {json.dumps({'table': parsed.get('table'), 'operation': parsed.get('operation')})}\n\n"
