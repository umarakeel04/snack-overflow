"""Repeatable demo data (not a production account provisioning strategy)."""
import os
from sqlalchemy import select
from .database import Base, SessionLocal, engine
from .models import Snack, User, Vote
from .security import hash_password
from .realtime import install_notification_triggers

SNACKS = [
    ("Masala Peanuts", "savoury", 3, 5),
    ("Dark Chocolate Cookies", "sweet", 18, 5),
    ("Baked Banana Chips", "savoury", 7, 5),
    ("Cold Brew Coffee", "drink", 0, 4),
    ("Granola Bars", "healthy-ish", 12, 5),
    ("Salted Popcorn", "savoury", 2, 5),
    ("Mango Juice", "drink", 9, 4),
    ("Roasted Almonds", "healthy-ish", 4, 5),
    ("Chocolate Wafers", "sweet", 0, 5),
    ("Green Tea", "drink", 22, 5),
    ("Trail Mix", "healthy-ish", 6, 5),
    ("Butter Cookies", "sweet", 15, 5),
]


def demo_accounts():
    # Local Docker Compose keeps its existing sample users for the assignment.
    # Public deployments MUST provide private, non-default credentials through
    # the hosting platform's secret variables, never a committed .env.
    if os.getenv("PUBLIC_DEMO_MODE", "").lower() in {"1", "true", "yes"}:
        names = (
            ("Pantry Admin", "DEMO_ADMIN_EMAIL", "DEMO_ADMIN_PASSWORD", "admin"),
            ("Office Member", "DEMO_MEMBER_EMAIL", "DEMO_MEMBER_PASSWORD", "member"),
        )
        result = []
        for name, email_key, password_key, role in names:
            email = os.getenv(email_key, "").strip().lower()
            password = os.getenv(password_key, "")
            if not email or not password or len(password) < 12 or password in {"Admin123!", "Member123!"}:
                raise RuntimeError(f"Public demo requires non-default {email_key} and {password_key} (12+ character password)")
            result.append((name, email, password, role))
        if result[0][1] == result[1][1]:
            raise RuntimeError("Public demo admin and member emails must differ")
        return result
    return [
        ("Pantry Admin", "admin@snackoverflow.dev", "Admin123!", "admin"),
        ("Office Member", "member@snackoverflow.dev", "Member123!", "member"),
    ]


def seed():
    Base.metadata.create_all(engine)
    install_notification_triggers(engine)
    with SessionLocal() as db:
        accounts = demo_accounts()
        for name, email, password, role in accounts:
            if not db.scalar(select(User).where(User.email == email)):
                db.add(User(name=name, email=email, password_hash=hash_password(password), role=role))
        for name, category, quantity, threshold in SNACKS:
            if not db.scalar(select(Snack).where(Snack.name == name)):
                db.add(Snack(name=name, category=category, quantity=quantity, low_stock_threshold=threshold))
        db.commit()
        admin_id = db.scalar(select(User.id).where(User.email == accounts[0][1]))
        member_id = db.scalar(select(User.id).where(User.email == accounts[1][1]))
        favorite_id = db.scalar(select(Snack.id).where(Snack.name == "Dark Chocolate Cookies"))
        for user_id in [admin_id, member_id]:
            if not db.get(Vote, (user_id, favorite_id)):
                db.add(Vote(user_id=user_id, snack_id=favorite_id))
        db.commit()
    print("Snack Overflow demo seed ready. Credentials are never printed to logs.")


if __name__ == "__main__":
    seed()
