"""Exactly-once stock mutation for each successful (user_id, Idempotency-Key).

The unique primary key is claimed *inside the same transaction* as the stock
UPDATE, audit INSERT, and saved response. A competing INSERT with the same
key blocks on PostgreSQL's unique index until the first transaction commits.
Then it reads and replays that response, rather than consuming twice.
"""
import json
from collections.abc import Callable
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session
from .models import ConsumeIdempotency
from .services import InventoryFailure, consume_stock


def consume_once(
    db: Session, user_id: int, key: str, snack_id: int, amount: int,
    snapshot: Callable[[], dict],
) -> dict:
    """Consume once or replay the original response for the same key + request.

    We support PostgreSQL (deployment) and SQLite (isolated tests). Both have
    INSERT ... ON CONFLICT DO NOTHING, so a unique constraint resolves races.
    Errors roll back the uncommitted key claim and all inventory changes.
    """
    table = ConsumeIdempotency.__table__
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = pg_insert(table)
    elif dialect == "sqlite":
        statement = sqlite_insert(table)
    else:
        raise RuntimeError("Idempotency currently supports PostgreSQL and SQLite")

    try:
        # Do NOT rely on Result.rowcount for INSERT ... ON CONFLICT.
        # Some PostgreSQL/driver combinations report -1 (unknown) rather than
        # 0 for a conflict, which could incorrectly execute consume_stock.
        # RETURNING is authoritative: one returned row means this transaction
        # inserted the unique receipt; no returned row means replay instead.
        claimed_user_id = db.execute(
            statement.values(user_id=user_id, key=key, snack_id=snack_id,
                             amount=amount, response_json="{}")
            .on_conflict_do_nothing(index_elements=["user_id", "key"])
            .returning(table.c.user_id)
        ).scalar_one_or_none()
        if claimed_user_id is None:
            receipt = db.scalar(select(ConsumeIdempotency).where(
                ConsumeIdempotency.user_id == user_id, ConsumeIdempotency.key == key
            ))
            if receipt is None:
                # Defensive guard: a conflict must have a corresponding row.
                raise RuntimeError("Idempotency receipt disappeared")
            if receipt.snack_id != snack_id or receipt.amount != amount:
                raise InventoryFailure(409, "IDEMPOTENCY_KEY_REUSED",
                                       "This Idempotency-Key was already used for a different consume request")
            return json.loads(receipt.response_json)

        # No commit yet: stock, audit and saved response succeed or fail together.
        consume_stock(db, snack_id, user_id, amount, commit=False)
        payload = snapshot()
        db.execute(update(ConsumeIdempotency).where(
            ConsumeIdempotency.user_id == user_id, ConsumeIdempotency.key == key
        ).values(response_json=json.dumps(payload)))
        db.commit()
        return payload
    except Exception:
        db.rollback()
        raise
