"""Database constraints enforce the invariants independent of API code."""
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def utcnow():
    # Naive UTC timestamps work on both SQLite and Postgres; document the convention.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'member')", name="ck_user_role"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(12), nullable=False)


class Snack(Base):
    __tablename__ = "snacks"
    __table_args__ = (
        CheckConstraint("category IN ('sweet','savoury','drink','healthy-ish')", name="ck_snack_category"),
        CheckConstraint("quantity >= 0 AND quantity <= 1000000", name="ck_quantity_range"),
        CheckConstraint("low_stock_threshold >= 0 AND low_stock_threshold <= 1000000", name="ck_threshold_range"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (UniqueConstraint("user_id", "snack_id", name="uq_vote_user_snack"),)
    # Composite primary key ALSO makes duplicate votes impossible at the DB level.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    snack_id: Mapped[int] = mapped_column(ForeignKey("snacks.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint("action IN ('consumed', 'restocked')", name="ck_activity_action"),
        CheckConstraint("amount > 0", name="ck_activity_amount"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    # Keep historical records even if admins remove a snack.
    snack_id: Mapped[int | None] = mapped_column(ForeignKey("snacks.id", ondelete="SET NULL"), nullable=True)
    snack_name: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
