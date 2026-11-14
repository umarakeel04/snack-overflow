"""Isolated SQLite database for fast API contract tests (Postgres tests are separate)."""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/snackoverflow-test-import.db")
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from app.database import Base, build_engine, get_db
from app.main import app
from app.models import Snack, User
from app.security import hash_password


@pytest.fixture
def setup(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'snacks-test.db'}")
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionFactory() as db:
        admin = User(name="Demo Admin", email="admin@test.dev", password_hash=hash_password("Password123!"), role="admin")
        member = User(name="Demo Member", email="member@test.dev", password_hash=hash_password("Password123!"), role="member")
        snack = Snack(name="Masala Peanuts", category="savoury", quantity=3, low_stock_threshold=5)
        db.add_all([admin, member, snack])
        db.commit()
        ids = {"admin": admin.id, "member": member.id, "snack": snack.id}

    def test_db():
        with SessionFactory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, SessionFactory, ids
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def auth(setup):
    client, _, _ = setup
    def login(email):
        response = client.post("/auth/login", json={"email": email, "password": "Password123!"})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['token']}"}
    return {"admin": login("admin@test.dev"), "member": login("member@test.dev")}
