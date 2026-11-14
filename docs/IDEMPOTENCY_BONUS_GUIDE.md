# Idempotency Bonus — implementation and testing guide

This patch is based on the **member sign-up version** of Snack Overflow. Apply it to the existing project, not to a fresh copy of the original submission.

## Why it matters

Your original database-level conditional `UPDATE` already prevents **overselling** when 10 *different* requests race for three packets (3 × HTTP 200, 7 × HTTP 409). However, one user's HTTP request may succeed on the server but appear to fail on the client when the network drops. Blindly retrying could consume twice.

The bonus adds an optional `Idempotency-Key` header to `POST /snacks/{id}/consume`. A given `(user_id, key)` can cause **at most one successful consumption**. It is safe across server processes, not merely inside Python memory.

## Request behavior

| Situation | Outcome |
| --- | --- |
| New key + amount 1, stock available | 200; decrement once; insert one audit row and receipt atomically |
| Same user, same key, same snack, same amount again | 200; exact same saved response, no extra stock or activity |
| Same user, same key, different snack or amount | 409 `IDEMPOTENCY_KEY_REUSED`; no mutation |
| Different user, same textual key | Independent operation (different user scope) |
| Missing key | Original endpoint behavior (backward-compatible) |
| Invalid key | 422 `INVALID_IDEMPOTENCY_KEY` |
| First attempt fails before commit | Whole transaction rolls back, including key; retry may proceed |

The frontend generates a UUID for a consume dialog and keeps it for retries of the **same amount**. Editing the amount creates a new key. Vote, add, edit, delete and restock APIs are unchanged.

## Safe installation on Windows

1. Save or commit your recent sign-up edits before applying this patch. If you edited `README.md` directly on GitHub, first synchronize your local branch when it is safe to do so.
2. Extract `Snack_Overflow_Idempotency_Update.zip` and **merge its `backend/`, `frontend/`, `docs/`, `scripts/`, and `README.md` paths into your existing project root** (`C:\Snack Overflow\snack-overflow`). Replace the *listed patch files only*. Do not replace `.env` or delete your database volume.
3. From the project root, rebuild:

```powershell
docker compose up -d --build backend frontend
```

The backend runs `python -m app.seed` at startup. Its `Base.metadata.create_all(engine)` creates the **new** `consume_idempotency` table if missing, while leaving existing tables and data untouched.

## Automated and live tests

```powershell
cd "C:\Snack Overflow\snack-overflow\backend"
.\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run build
cd ..
python scripts/smoke_http.py
python scripts/smoke_idempotency.py
```

Local test expectation: **25 passed, 2 skipped** if `TEST_POSTGRES_URL` is not set. The old race test and new parallel-key test require PostgreSQL; GitHub CI has a Postgres service and will run both. The frontend build must be confirmed on your own machine.

Expected live output (counts are deterministic if the backend is working):

```text
10 simultaneous HTTP requests, SAME key: 10 x 200; quantity 3 -> 2 (once only).
Same key with DIFFERENT amount: 409 IDEMPOTENCY_KEY_REUSED.
Late retry with original key: original 200 body replayed.
Exactly one activity record: VERIFIED.
PASS: same-key concurrent retries cannot double-consume.
```

**Comparison:** In `smoke_http.py`, every concurrent request deliberately omits the key: three separate consumes succeed and seven fail. In `smoke_idempotency.py`, ten requests use **the same key**, meaning one logical consume retried ten times: all return the saved 200 result but only one packet is taken.

## What to show a recruiter

Open `backend/app/models.py` (`ConsumeIdempotency`), `backend/app/idempotency.py` (`consume_once`), and `backend/app/main.py` (`consume`). Explain:

1. Unique `(user_id, key)` **primary key** is enforced by PostgreSQL.
2. `INSERT ... ON CONFLICT DO NOTHING` makes a competing request wait for the winner's commit and then replay the original response.
3. Atomic SQL stock decrement, activity insert, and receipt response commit **together**.
4. A mismatched payload gets 409 so a key cannot silently be repurposed.
5. The response is a **snapshot**, not guaranteed to show the latest stock if others have consumed more since it was first saved.

## Known trade-offs

- This optional header protects consuming, not every write endpoint. That is the scope of the bonus.
- Receipts are not automatically pruned in this demo. Production needs an explicit retention period and cleanup task. Deleting a user cascades their receipts; deleting a snack does not invalidate its previously saved receipt.
- `create_all()` is a demo-friendly additive table setup; use Alembic migrations in production.
- The client retains a key only while that consume dialog stays open; a new dialog represents a new user intent. Robust production clients may persist pending operation keys across app restarts.
- Rate limiting, metrics, and cancellation/timeout policy are future production improvements.

## Pushing the patch

After tests and the frontend build pass, from the project root:

```powershell
git add README.md backend/app/main.py backend/app/models.py backend/app/services.py backend/app/idempotency.py backend/tests/test_idempotency.py frontend/src/App.tsx frontend/src/api.ts scripts/smoke_idempotency.py docs/IDEMPOTENCY_BONUS_GUIDE.md
git commit -m "feat: add database-backed consume idempotency"
git pull --rebase origin main
git push origin main
```

If `git pull --rebase` reports a conflict, resolve it before pushing; never force-push. Check GitHub Actions again and verify both the FastAPI/PostgreSQL and React jobs are green.
