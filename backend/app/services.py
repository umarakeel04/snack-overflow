"""Inventory operations. SQL (not Python) is the authority for stock levels."""
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .config import MAX_QUANTITY
from .models import Snack, Activity
from .schemas import AmountIn


class InventoryFailure(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def consume_stock(db: Session, snack_id: int, user_id: int, amount: int, *, commit: bool = True) -> None:
    """One atomic conditional UPDATE and audit INSERT in a single DB transaction.

    Under PostgreSQL READ COMMITTED, competing UPDATEs acquire a row lock;
    after waking, the WHERE quantity >= amount condition is re-evaluated.
    No SELECT-then-UPDATE race or process-local lock is involved.
    """
    result = db.execute(
        update(Snack)
        .where(Snack.id == snack_id, Snack.quantity >= amount)
        .values(quantity=Snack.quantity - amount)
        .returning(Snack.name)
    ).first()
    if result is None:
        exists = db.scalar(select(Snack.id).where(Snack.id == snack_id))
        if exists is None:
            raise InventoryFailure(404, "SNACK_NOT_FOUND", "Snack not found")
        raise InventoryFailure(409, "INSUFFICIENT_STOCK", "Someone beat you to the last packet! Not enough stock remains.")
    db.add(Activity(user_id=user_id, snack_id=snack_id, snack_name=result.name,
                    action="consumed", amount=amount))
    if commit:
        db.commit()  # UPDATE and activity commit together; failure rolls both back.
    # With commit=False, the caller owns the transaction (idempotent consume).


def restock(db: Session, snack_id: int, user_id: int, amount: int) -> None:
    result = db.execute(
        update(Snack)
        .where(Snack.id == snack_id, Snack.quantity <= MAX_QUANTITY - amount)
        .values(quantity=Snack.quantity + amount)
        .returning(Snack.name)
    ).first()
    if result is None:
        exists = db.scalar(select(Snack.id).where(Snack.id == snack_id))
        if exists is None:
            raise InventoryFailure(404, "SNACK_NOT_FOUND", "Snack not found")
        raise InventoryFailure(409, "STOCK_LIMIT", "Restock would exceed the allowed quantity limit")
    db.add(Activity(user_id=user_id, snack_id=snack_id, snack_name=result.name,
                    action="restocked", amount=amount))
    db.commit()
