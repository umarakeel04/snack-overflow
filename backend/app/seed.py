"""Repeatable demo data (not a production account provisioning strategy)."""
from sqlalchemy import select
from .database import Base, SessionLocal, engine
from .models import Snack, User, Vote
from .security import hash_password

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


def seed():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        demo_accounts = [
            ("Pantry Admin", "admin@snackoverflow.dev", "Admin123!", "admin"),
            ("Office Member", "member@snackoverflow.dev", "Member123!", "member"),
        ]
        for name, email, password, role in demo_accounts:
            if not db.scalar(select(User).where(User.email == email)):
                db.add(User(name=name, email=email, password_hash=hash_password(password), role=role))
        for name, category, quantity, threshold in SNACKS:
            if not db.scalar(select(Snack).where(Snack.name == name)):
                db.add(Snack(name=name, category=category, quantity=quantity, low_stock_threshold=threshold))
        db.commit()
        admin_id = db.scalar(select(User.id).where(User.email == "admin@snackoverflow.dev"))
        member_id = db.scalar(select(User.id).where(User.email == "member@snackoverflow.dev"))
        favorite_id = db.scalar(select(Snack.id).where(Snack.name == "Dark Chocolate Cookies"))
        for user_id in [admin_id, member_id]:
            if not db.get(Vote, (user_id, favorite_id)):
                db.add(Vote(user_id=user_id, snack_id=favorite_id))
        db.commit()
    print("Demo seed ready. Admin: admin@snackoverflow.dev / Admin123!; Member: member@snackoverflow.dev / Member123!")


if __name__ == "__main__":
    seed()
