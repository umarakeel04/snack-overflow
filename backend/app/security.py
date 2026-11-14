"""Password hashing via standard-library scrypt and opaque, revocable sessions."""
import hashlib
import hmac
import secrets
from datetime import timedelta
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import SESSION_HOURS
from .database import get_db
from .models import LoginSession, User, utcnow


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        tested = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(tested, bytes.fromhex(digest))
    except (ValueError, TypeError, MemoryError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=token_digest(token), user_id=user_id, expires_at=utcnow() + timedelta(hours=SESSION_HOURS)))
    db.commit()
    return token


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Login is required")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "Login is required")
    user = db.scalar(select(User).join(LoginSession, LoginSession.user_id == User.id).where(
        LoginSession.token_hash == token_digest(token), LoginSession.expires_at > utcnow()
    ))
    if user is None:
        raise HTTPException(401, "Your session has expired; please sign in again")
    return user


def admin_only(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Admin access is required")
    return user
