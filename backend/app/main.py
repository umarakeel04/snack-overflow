"""Snack Overflow REST API. Start with: uvicorn app.main:app --reload"""
from datetime import timedelta
import re
from math import ceil
import logging
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import and_, case, delete, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .config import FRONTEND_ORIGINS
from .database import get_db
from .models import Activity, LoginSession, Snack, User, Vote, utcnow
from .schemas import (
    ActivityOut, ActivityPage, AmountIn, Category, Credentials, LoginOut,
    SnackCreate, SnackOut, SnackPage, SnackPatch, Status, SummaryOut, UserOut, WinnerOut, RegistrationIn,
)
from .security import admin_only, create_session, current_user, hash_password, token_digest, verify_password
from .services import InventoryFailure, consume_stock, restock
from .idempotency import consume_once
from .realtime import CHANNEL, format_change_event
from .config import DATABASE_URL

log = logging.getLogger(__name__)
app = FastAPI(title="Snack Overflow API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_ORIGINS,
                   allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "DELETE"],
                   allow_headers=["Authorization", "Content-Type", "Idempotency-Key"])


def fail(status: int, code: str, message: str):
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and {"code", "message"} <= detail.keys():
        error = detail
    else:
        error = {"code": {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND"}.get(
            exc.status_code, "REQUEST_FAILED"), "message": str(detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": error})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(x) for x in e["loc"]), "reason": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"error": {
        "code": "VALIDATION_ERROR", "message": "Please check the supplied values", "details": details
    }})


@app.exception_handler(InventoryFailure)
async def inventory_exception_handler(_request: Request, exc: InventoryFailure):
    return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    log.exception("Unexpected API error", exc_info=exc)
    return JSONResponse(status_code=500, content={"error": {
        "code": "INTERNAL_ERROR", "message": "An unexpected error occurred"
    }})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginOut)
def login(body: Credentials, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        fail(401, "INVALID_CREDENTIALS", "Invalid email or password")
    return LoginOut(token=create_session(db, user.id), user=UserOut.model_validate(user))


@app.post("/auth/register", response_model=LoginOut, status_code=201)
def register(body: RegistrationIn, db: Session = Depends(get_db)):
    """Create a member only. Email uniqueness is enforced by the database."""
    user = User(name=body.name, email=str(body.email).lower(),
                password_hash=hash_password(body.password), role="member")
    db.add(user)
    try:
        # Flush obtains the new user ID and checks uniqueness without committing.
        db.flush()
        # create_session commits both the user and their initial session together.
        token = create_session(db, user.id)
    except IntegrityError:
        db.rollback()
        fail(409, "EMAIL_ALREADY_REGISTERED", "This email address is already registered. Please sign in.")
    return LoginOut(token=token, user=UserOut.model_validate(user))


@app.post("/auth/logout", status_code=204)
def logout(request: Request, _user: User = Depends(current_user), db: Session = Depends(get_db)):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    db.execute(delete(LoginSession).where(LoginSession.token_hash == token_digest(token)))
    db.commit()
    return Response(status_code=204)


@app.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return UserOut.model_validate(user)


def status_sql():
    return case((Snack.quantity == 0, "gone"),
                (Snack.quantity <= Snack.low_stock_threshold, "running_low"), else_="stocked")


def as_snack(snack: Snack, votes: int, user_id: int, voted_ids: set[int]) -> SnackOut:
    quantity = snack.quantity
    status = "gone" if quantity == 0 else "running_low" if quantity <= snack.low_stock_threshold else "stocked"
    return SnackOut(id=snack.id, name=snack.name, category=snack.category, quantity=quantity,
                    low_stock_threshold=snack.low_stock_threshold, status=status,
                    votes=votes, has_voted=snack.id in voted_ids)


def vote_count_sql():
    return select(func.count(Vote.user_id)).where(Vote.snack_id == Snack.id).correlate(Snack).scalar_subquery()


def voted_ids_for(db: Session, user_id: int, ids: list[int]) -> set[int]:
    if not ids:
        return set()
    return set(db.scalars(select(Vote.snack_id).where(Vote.user_id == user_id, Vote.snack_id.in_(ids))).all())


# Authenticated SSE stream. Native EventSource cannot send a Bearer header, so
# the React client uses streaming fetch and never puts the token in the URL.
# Declare this literal route BEFORE /snacks/{snack_id}.
@app.get("/snacks/events")
async def pantry_events(request: Request, _user: User = Depends(current_user)):
    if not DATABASE_URL.startswith("postgresql+"):
        fail(503, "REALTIME_UNAVAILABLE", "Real-time updates require PostgreSQL")

    async def generate():
        import psycopg

        dsn = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)
        try:
            async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as connection:
                await connection.execute(f"LISTEN {CHANNEL}")
                # A connected frame lets the client reconcile writes that occurred
                # between its initial GET and the LISTEN becoming active.
                yield "event: connected\ndata: {}\n\n"
                while not await request.is_disconnected():
                    async for notification in connection.notifies(timeout=15):
                        yield format_change_event(notification.payload)
                    yield ": keepalive\n\n"
        except Exception:
            log.exception("Real-time SSE stream disconnected")
            # The fetch client reconnects on EOF or a stream error.

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no",
    })


# Declare the literal /summary route BEFORE /{snack_id}.
@app.get("/snacks/summary", response_model=SummaryOut)
def summary(_user: User = Depends(current_user), db: Session = Depends(get_db)):
    status = status_sql()
    grouped = dict(db.execute(select(status, func.count(Snack.id)).group_by(status)).all())
    cutoff = utcnow() - timedelta(days=7)
    winner = db.execute(
        select(Snack, func.count(Vote.user_id).label("weekly_votes"))
        .join(Vote, and_(Vote.snack_id == Snack.id, Vote.created_at >= cutoff))
        .group_by(Snack.id)
        .order_by(desc("weekly_votes"), Snack.name.asc(), Snack.id.asc())
        .limit(1)
    ).first()
    return SummaryOut(
        stocked=grouped.get("stocked", 0), running_low=grouped.get("running_low", 0),
        gone=grouped.get("gone", 0), total=sum(grouped.values()),
        snack_of_the_week=WinnerOut(id=winner[0].id, name=winner[0].name,
            category=winner[0].category, votes_this_week=winner[1]) if winner else None,
    )


@app.get("/snacks", response_model=SnackPage)
def list_snacks(
    q: str = Query(default="", max_length=120),
    category: Category | None = None,
    status: Status | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=8, ge=1, le=50),
    sort: str = Query(default="name", pattern="^(name|quantity|votes)$"),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    user: User = Depends(current_user), db: Session = Depends(get_db),
):
    conditions = []
    if q.strip():
        conditions.append(Snack.name.ilike(f"%{q.strip()}%"))
    if category:
        conditions.append(Snack.category == category)
    if status:
        conditions.append(status_sql() == status)
    total = db.scalar(select(func.count(Snack.id)).where(*conditions)) or 0
    votes_expr = vote_count_sql()
    sort_expr = {"name": Snack.name, "quantity": Snack.quantity, "votes": votes_expr}[sort]
    sort_expr = sort_expr.desc() if order == "desc" else sort_expr.asc()
    rows = db.execute(select(Snack, votes_expr.label("votes"))
        .where(*conditions).order_by(sort_expr, Snack.id.asc())
        .limit(page_size).offset((page - 1) * page_size)).all()
    voted_ids = voted_ids_for(db, user.id, [snack.id for snack, _ in rows])
    return SnackPage(items=[as_snack(snack, votes, user.id, voted_ids) for snack, votes in rows],
                     total=total, page=page, page_size=page_size, pages=ceil(total / page_size))


@app.get("/snacks/{snack_id}", response_model=SnackOut)
def get_snack(snack_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    snack = db.get(Snack, snack_id)
    if snack is None:
        fail(404, "SNACK_NOT_FOUND", "Snack not found")
    votes = db.scalar(select(func.count()).select_from(Vote).where(Vote.snack_id == snack_id)) or 0
    voted = voted_ids_for(db, user.id, [snack_id])
    return as_snack(snack, votes, user.id, voted)


@app.post("/snacks", response_model=SnackOut, status_code=201)
def create_snack(body: SnackCreate, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    snack = Snack(**body.model_dump())
    db.add(snack)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "DUPLICATE_SNACK", "A snack with this name already exists")
    db.refresh(snack)
    return as_snack(snack, 0, user.id, set())


@app.patch("/snacks/{snack_id}", response_model=SnackOut)
def edit_snack(snack_id: int, body: SnackPatch, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    snack = db.get(Snack, snack_id)
    if snack is None:
        fail(404, "SNACK_NOT_FOUND", "Snack not found")
    changes = body.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        fail(422, "VALIDATION_ERROR", "Fields cannot be null")
    for key, value in changes.items():
        setattr(snack, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "DUPLICATE_SNACK", "A snack with this name already exists")
    return get_snack(snack_id, user, db)


@app.delete("/snacks/{snack_id}", status_code=204)
def remove_snack(snack_id: int, _user: User = Depends(admin_only), db: Session = Depends(get_db)):
    snack = db.get(Snack, snack_id)
    if snack is None:
        fail(404, "SNACK_NOT_FOUND", "Snack not found")
    db.delete(snack)
    db.commit()
    return Response(status_code=204)


@app.post("/snacks/{snack_id}/consume", response_model=SnackOut)
def consume(
    snack_id: int, body: AmountIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user), db: Session = Depends(get_db),
):
    if idempotency_key is None:
        # Backward-compatible: old clients / concurrency smoke test remain unchanged.
        consume_stock(db, snack_id, user.id, body.amount)
        return get_snack(snack_id, user, db)
    if not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key):
        fail(422, "INVALID_IDEMPOTENCY_KEY",
             "Idempotency-Key must be 8-128 letters, digits, periods, underscores, colons or hyphens")
    return consume_once(
        db, user.id, idempotency_key, snack_id, body.amount,
        lambda: get_snack(snack_id, user, db).model_dump(mode="json"),
    )


@app.post("/snacks/{snack_id}/restock", response_model=SnackOut)
def restock_route(snack_id: int, body: AmountIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    restock(db, snack_id, user.id, body.amount)
    return get_snack(snack_id, user, db)


@app.post("/snacks/{snack_id}/vote", response_model=SnackOut, status_code=201)
def vote(snack_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(Snack, snack_id) is None:
        fail(404, "SNACK_NOT_FOUND", "Snack not found")
    db.add(Vote(user_id=user.id, snack_id=snack_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "ALREADY_VOTED", "You already voted for this snack")
    return get_snack(snack_id, user, db)


@app.delete("/snacks/{snack_id}/vote", response_model=SnackOut)
def unvote(snack_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(Snack, snack_id) is None:
        fail(404, "SNACK_NOT_FOUND", "Snack not found")
    removed = db.execute(delete(Vote).where(Vote.user_id == user.id, Vote.snack_id == snack_id))
    if removed.rowcount == 0:
        fail(409, "NOT_VOTED", "You have not voted for this snack")
    db.commit()
    return get_snack(snack_id, user, db)


@app.get("/activity", response_model=ActivityPage)
def activity(page: int = Query(default=1, ge=1), page_size: int = Query(default=10, ge=1, le=50),
             _user: User = Depends(admin_only), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(Activity.id))) or 0
    rows = db.execute(select(Activity, User.name).join(User, User.id == Activity.user_id)
        .order_by(Activity.created_at.desc(), Activity.id.desc())
        .limit(page_size).offset((page - 1) * page_size)).all()
    return ActivityPage(items=[ActivityOut(id=a.id, user_name=name, snack_name=a.snack_name,
        action=a.action, amount=a.amount, created_at=a.created_at.isoformat() + "Z") for a, name in rows],
        total=total, page=page, page_size=page_size, pages=ceil(total / page_size))
