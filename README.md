# 🍿 Snack Overflow

> A full-stack office pantry tracker built for Bipolar Factory's Full Stack Intern — Round 2 assignment.

**Live demo:** [Open Snack Overflow](https://frontend-production-03621756.up.railway.app/) · **Source:** [GitHub repository](https://github.com/umarakeel04/snack-overflow) · **CI:** [GitHub Actions](https://github.com/umarakeel04/snack-overflow/actions)

**Stack:** React 18 · TypeScript · Vite · FastAPI · SQLAlchemy 2 · PostgreSQL 16 · Docker Compose · Pytest · Ruff · ESLint · Railway

Snack Overflow lets office members browse snacks, vote for favourites, and consume packets while maintaining accurate stock. Admins manage inventory, restock items, and inspect activity history. The core engineering requirement is enforced in PostgreSQL: even when ten people compete for the final three packets, stock cannot go negative.

### Reviewer quick start

1. **Try the hosted UI:** [Live demo](https://frontend-production-03621756.up.railway.app/). Reviewers can use credentials supplied **privately in the submission email**; public registration creates member accounts only.
2. **Review the concurrency design:** [Atomic stock update](#-the-concurrency-guarantee) and [idempotent retries](#idempotent-consume-retries-bonus).
3. **Verify quality:** [Tests and CI](#-testing-and-ci), [`scripts/smoke_http.py`](scripts/smoke_http.py), and [`scripts/smoke_idempotency.py`](scripts/smoke_idempotency.py).
4. **Understand trade-offs:** [Design note](#-short-design-note-decisions-trade-offs-100-users), [real-time updates](#-real-time-pantry-updates-bonus), and [public deployment](#-public-deployment-live-demo-bonus).

> **Public demo notice:** This is a time-boxed internship demonstration, not a production identity service. The hosted database is separate from local Docker data, and its admin/member credentials are never committed to Git.

## 🚀 Run it locally with Docker Compose

Prerequisites: [Docker Desktop](https://docs.docker.com/desktop/) with Compose enabled, and Git.

```bash
git clone https://github.com/umarakeel04/snack-overflow.git
cd snack-overflow
cp .env.example .env
# On Windows PowerShell, use: Copy-Item .env.example .env
docker compose up --build
```

Use your own local database password in the gitignored `.env` file before starting the stack. The repository's sample accounts below are **local-only**. The hosted Railway application uses different, private credentials.

Open:

- **Web app:** http://localhost:3000
- **Interactive API docs:** http://localhost:8000/docs
- **API health:** http://localhost:8000/health

The backend automatically creates tables and seeds demo data on container startup. The seed script is **idempotent**: existing stock changes, activity, and votes are not reset when you restart. Docker Compose binds the PostgreSQL server on `localhost:5433`, so it will not collide with a typical local PostgreSQL on `5432`.

> **Note:** `.env.example` contains a *placeholder local development password* for convenience. Set your own value in `.env`, which is gitignored. This configuration and the demo accounts are **not for public production deployment**. Changing the DB password after its volume was initialized also requires updating the stored DB user's password (or removing the local demo volume).

### Demo credentials

| Role | Email | Password | Capabilities |
| --- | --- | --- | --- |
| Admin | `admin@snackoverflow.dev` | `Admin123!` | Everything, including management, restock, and activity |
| Member | `member@snackoverflow.dev` | `Member123!` | Browse, search, consume, vote/unvote |

**Important:** These passwords are intentionally **local-only**. They are not used on Railway. Public demo credentials are provisioned via the backend's private `DEMO_*` variables and shared with reviewers separately; do not put those passwords into this README or a screenshot.

### Run without Docker (optional)

You need a PostgreSQL server/database accessible from your machine, Node.js 22+ (needed for the frontend's standalone TypeScript tests), and Python 3.11+. Configure `DATABASE_URL` in `backend/.env`, using `backend/.env.example` as a starting point. Use a development database, not your Railway database.

Terminal A (API):

```bash
cd backend
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
# Copy .env.example to .env and change DATABASE_URL to your local connection
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

Terminal B (React):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` to port `8000`; the Docker Nginx frontend does the same.

## ✅ Feature checklist

| Requirement | Implementation |
| --- | --- |
| Demo login | Hashed seeded passwords, opaque random session token, revocable hashed token in database |
| Role-aware interface | Member sees only permitted actions; admin sees Add/Restock/Edit/Delete/Activity |
| Protected API | All protected routes enforce login; management and restock enforce `admin` on server |
| Snack inventory | Add, edit, delete, get details; derived status from quantity and threshold |
| Search, category/status filters | Server-side queries; no filtering the current frontend page as a substitute |
| Pagination and sorting | Server-side page/page_size, sort by name, quantity, votes |
| Dashboard | Counts by status and Snack of the Week (most votes in the last seven days) |
| Consume | Atomic conditional DB update with 409 when stock is insufficient; optional `Idempotency-Key` for safe retries |
| Restock | Atomic conditional DB update with max quantity safety |
| Vote/unvote | Composite database primary key `(user_id, snack_id)` prevents duplicates |
| Activity history | Consume and restock activity inserted in the same transaction as stock change |
| Validation | Pydantic request models + SQL `CHECK` constraints; unknown fields rejected |
| Error states | Consistent `{ "error": { "code", "message" } }` and validation details |
| Tests | HTTP contract tests, 10-worker race, rollback test; optional real PostgreSQL race in CI |
| Responsive UI | CSS grid cards, mobile-friendly filters, modal forms, feedback and empty states |
| Member sign-up | `POST /auth/register` creates a member-only account with server-side role enforcement |
| Optimistic UI | Immediate vote/consume previews; rollback and error feedback if the API rejects the operation |
| Real-time synchronization | Authenticated SSE backed by PostgreSQL `LISTEN/NOTIFY` refreshes other open sessions |
| Public demo | Railway hosting: public React/Nginx frontend, private FastAPI service, managed PostgreSQL |

### All nine optional bonuses

| Bonus | Implementation |
| --- | --- |
| Docker | One `docker compose up --build` starts database, API and UI |
| Sign-up | Member registration via `/auth/register` |
| Activity page | Admin-only, paginated activity history |
| Optimistic UI | Immediate vote/consume previews with automatic rollback |
| Real-time updates | Cross-tab stock and vote updates using PostgreSQL notifications + SSE |
| Idempotency | `Idempotency-Key` prevents retried consumption from decrementing stock twice |
| Sorting | Server-side sort by name, quantity or votes |
| CI pipeline | Ruff, ESLint, type-check, frontend tests, backend tests including PostgreSQL |
| Live demo | [Railway-hosted site](https://frontend-production-03621756.up.railway.app/) |

## 🧱 Architecture

```text
      Browser (member / admin)
                 |
       HTTPS (public Railway URL)
                 |
      React + TypeScript / Vite
      Nginx (static UI and /api proxy)
                 |
    Private backend connection (Railway)
                 |
        FastAPI + Pydantic
      Auth / role guards / REST
      Atomic inventory transactions
                 |
       SQLAlchemy / PostgreSQL 16
      users, sessions, snacks, votes,
      activities, consume_idempotency
                 |
      PostgreSQL trigger on mutations
                 |
        LISTEN / NOTIFY --------------+
                 |                     |
        Authenticated SSE              |
                 |                     |
       Other open browser tabs <-------+
        (refetch authoritative data)
```

Locally, Docker Compose runs Nginx, FastAPI and PostgreSQL together. On Railway, only the frontend is public; Nginx proxies `/api` and the SSE stream to the private backend, which connects to private PostgreSQL.

The frontend never writes directly to PostgreSQL. FastAPI handles validation, authentication, authorization and transactions. PostgreSQL notifications are **invalidation signals**, not a replacement for REST reads: connected clients re-fetch the authoritative list/summary after a committed mutation. The database remains the source of truth.

### Schema choices

| Table | Main fields | Integrity |
| --- | --- | --- |
| `users` | `id`, `name`, `email`, `password_hash`, `role` | Unique email; role `admin/member`; scrypt salted hash, never plaintext |
| `login_sessions` | `id`, `user_id`, `token_hash`, `expires_at` | Only SHA-256 token *digests* are stored; session can be invalidated at logout |
| `snacks` | `id`, `name`, `category`, `quantity`, `low_stock_threshold`, `created_at` | Unique case-insensitive name index, category `CHECK`, quantity/threshold bounds `CHECK` |
| `votes` | `user_id`, `snack_id`, `created_at` | Composite primary key guarantees one vote per user/snack at DB level |
| `activities` | `id`, `user_id`, `snack_id`, `snack_name`, `action`, `amount`, `created_at` | Positive amount + valid action checks; same transaction as stock update |
| `consume_idempotency` | `(user_id, key)`, `snack_id`, `amount`, `response_json`, `created_at` | Composite primary key guarantees one result per user/key; stored response is replayable even if snack is later deleted |

**Derived status** (never a stored column):

- `gone`: `quantity == 0`
- `running_low`: `1 <= quantity <= low_stock_threshold`
- `stocked`: `quantity > low_stock_threshold`

Keeping status computed prevents the database from containing contradictory quantity and status values. `snack_name` is copied to each activity entry so the audit view still has a meaningful label after the snack is deleted; the foreign-key `snack_id` then becomes `NULL`.

**Snack of the Week:** The snack with the most *votes cast during the trailing seven days*. Ties break by snack name, then ID. A snack with no votes during that period is not declared a winner. Removing a vote removes its contribution. This is a deliberate, documented interpretation of the challenge's undefined winner rule.

## ⚡ The concurrency guarantee

**Scenario:** `Masala Peanuts.quantity = 3`. Ten people send `POST /snacks/{id}/consume` with `{"amount": 1}` at the same moment.

**Incorrect approach:** `SELECT quantity`, then in Python, `if quantity > 0: quantity -= 1; UPDATE`. Multiple requests can read the same stock before writing, leading to lost updates or overselling.

**Implemented approach** (`backend/app/services.py`):

```sql
UPDATE snacks
SET quantity = quantity - :amount
WHERE id = :snack_id AND quantity >= :amount
RETURNING name;
```

A single conditional statement executes **inside PostgreSQL**. When simultaneous updates target the same row, PostgreSQL locks the row and re-checks the `WHERE` condition when another transaction finishes (under the default `READ COMMITTED` isolation level). Exactly three statements update a row; seven find no eligible row. We distinguish missing snack (`404`) from insufficient stock (`409`). We do **not** depend on a thread/process lock, stale frontend state, or an initial read.

The successful SQL `UPDATE` and `INSERT INTO activities (...)` run within the **same database transaction** and commit together. If the audit insert fails, the stock decrement rolls back. The database also contains `CHECK (quantity >= 0)` as a second line of defence.

Restocks use the same pattern with `quantity <= MAX_QUANTITY - :amount` to prevent overflow.

### Idempotent consume retries (bonus)

The React client sends an `Idempotency-Key` (a UUID) when consuming. The key stays the same when retrying the **same snack and amount** in the open dialog after an uncertain network result; changing the amount generates a new key. An HTTP client may also send its own 8–128 character key (`A–Z`, `a–z`, `0–9`, `.`, `_`, `:`, `-`). The header is optional for compatibility with older clients.

PostgreSQL's primary key on `consume_idempotency (user_id, key)` is the single source of truth. For a new key, the API **claims the key, decrements stock, inserts activity and saves the response in one DB transaction**. Simultaneous requests with an identical key are serialized by the unique constraint; after the first commits, they replay its original `200` response **without consuming a second packet**. Same user/key with a different snack or amount returns `409 IDEMPOTENCY_KEY_REUSED`. Different users have separate key namespaces. In case of failure, the transaction rolls back, including the key claim, so the request can be retried after the problem is fixed.

This guarantees *at most one successful consumption per user/key*, not that every network request succeeds. The saved response is a historical snapshot, intentionally **not** today's live quantity. Call `GET /snacks/{id}` for current stock. Keys/receipts currently persist until account deletion; production scale would need a documented retention and cleanup policy (for example 24 hours after the last client retry window). New `consume_idempotency` table is created by the existing seed startup without deleting data; a production database would use migrations (Alembic).

Try the live HTTP demonstration after `docker compose up -d --build backend frontend`:

```powershell
python scripts/smoke_idempotency.py
```

It sends ten simultaneous requests with the **same** key for one packet. Expected: ten HTTP `200` replays, stock `3 -> 2`, exactly one activity, and a `409` when the same key is reused with another amount. This complements `python scripts/smoke_http.py`, which deliberately omits keys to demonstrate 3 successful / 7 conflicting *independent* consumption requests.

### Votes are safe under contention

The primary key on `votes (user_id, snack_id)` makes duplicate votes impossible, including two simultaneous clicks or HTTP requests. An attempted duplicate is caught as `IntegrityError` and translated to HTTP `409` with `ALREADY_VOTED`. It is **not** just a prior `SELECT` check.

## 🔐 Authentication and security

- `POST /auth/login` checks a per-user salted, scrypt-hashed password. The database never stores plaintext credentials.
- A successful login generates a cryptographically random bearer token. Only its SHA-256 digest is stored in `login_sessions`; it expires after 12 hours and logout deletes it.
- Every protected endpoint looks up the current user on the server; `admin_only` rejects members with HTTP `403` regardless of frontend visibility.
- Pydantic rejects malformed quantities, categories, names, unknown body keys (including direct quantity PATCH attempts), and invalid query parameters.
- Database `CHECK` constraints and primary/unique keys defend the data even if an app validation path is skipped.
- Real environment-specific credentials belong in gitignored `.env` files. Never commit deployment secrets, production connection strings, or real passwords.
- `sessionStorage` is used for the demo token, rather than persisting indefinitely. A public release should use secure HttpOnly/SameSite cookies, CSRF protection, HTTPS, rate limits, and monitoring.

## 📗 API contract

All routes except `POST /auth/login`, `POST /auth/register`, and `GET /health` require `Authorization: Bearer <session-token>`.

| Method | Endpoint | Role | Notes |
| --- | --- | --- | --- |
| `POST` | `/auth/login` | Public | Body: `{ "email", "password" }`; returns token + user |
| `POST` | `/auth/register` | Public | Body: `{ "name", "email", "password" }`; always creates a **member** and returns token + user (`201`), or duplicate-email `409` |
| `GET` | `/auth/me` | Any logged in | Current user |
| `POST` | `/auth/logout` | Any logged in | Revokes token; `204` |
| `GET` | `/health` | Public | Health response |
| `GET` | `/snacks` | Member/Admin | `q`, `category`, `status`, `page`, `page_size`, `sort`, `order` |
| `GET` | `/snacks/summary` | Member/Admin | Status counts + weekly winner |
| `GET` | `/snacks/{id}` | Member/Admin | Snack detail and vote status |
| `POST` | `/snacks` | Admin | Create `{name, category, quantity?, low_stock_threshold?}`; `201` |
| `PATCH` | `/snacks/{id}` | Admin | Edit `{name?, category?, low_stock_threshold?}` |
| `DELETE` | `/snacks/{id}` | Admin | Delete; `204` |
| `POST` | `/snacks/{id}/consume` | Member/Admin | `{ "amount": integer }`; optional `Idempotency-Key` header; `409` if not enough or key reused for different request |
| `POST` | `/snacks/{id}/restock` | Admin | `{ "amount": integer }`; `409` if max exceeded |
| `POST` | `/snacks/{id}/vote` | Member/Admin | `201`; `409` if already voted |
| `DELETE` | `/snacks/{id}/vote` | Member/Admin | Removes vote; `409` if not voted |
| `GET` | `/activity` | Admin | Audit log, paginated |
| `GET` | `/snacks/events` | Member/Admin | Authenticated SSE connection for pantry invalidation events |

Allowed categories: `sweet`, `savoury`, `drink`, `healthy-ish`. Stock statuses: `stocked`, `running_low`, `gone`. Sort: `name`, `quantity`, `votes`; order: `asc` or `desc`. Default page size: 8, maximum: 50.

### Errors (one shape throughout)

```json
{ "error": { "code": "INSUFFICIENT_STOCK", "message": "Someone beat you to the last packet! Not enough stock remains." } }
```

| HTTP | Meaning |
| --- | --- |
| `200` / `201` / `204` | Success (read/update / create / delete) |
| `401` | No valid session or wrong credentials |
| `403` | Valid member account, but not permitted |
| `404` | Unknown snack |
| `409` | Stock conflict, duplicate vote or duplicate snack |
| `422` | Request validation failure (includes `error.details`) |
| `500` | Unexpected server error (internal details are not exposed) |

### Example: consume a packet

```bash
# Get a demo session token first, e.g. via /docs or a REST client:
curl -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"member@snackoverflow.dev","password":"Member123!"}'

# Paste the returned token into TOKEN (don't commit it):
curl -X POST http://localhost:8000/snacks/1/consume \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: example-consume-12345' \
  -d '{"amount":1}'
```

## 🧹 Automated linting (CI bonus)

The GitHub Actions `CI` workflow runs on **every push and pull request**. It now checks:

- **Python:** Ruff static linting (`E4`, `E7`, `E9`, and `F` rules), plus Pytest, including real PostgreSQL contention tests. Existing compact single-line statement style is allowed by the documented Ruff configuration.
- **React/TypeScript:** ESLint recommended checks, TypeScript type-checking, and a Vite production build.

To run the checks on Windows before pushing:

```powershell
# At the repository root; use your existing virtual environment
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm install          # Updates package-lock.json when lint dependencies change
npm run lint
npm run test:optimistic
npm run test:realtime
npm run build
cd ..
```

Commit the updated `frontend/package-lock.json` after `npm install`, so GitHub Actions can use reproducible `npm ci`. Lint checks are intentionally separate from behavioral tests: **passing lint does not replace concurrency or security tests**.

## 🧪 Testing and CI

**Backend test suite** includes:

1. Login, invalid credentials, logout/revocation, missing auth.
2. Server-side member-vs-admin permission enforcement.
3. Create/edit/delete with invalid fields and duplicate names.
4. Search, filters, sorting, pagination, and derived dashboard status.
5. Vote/unvote, duplicate vote rejection and weekly winner.
6. Consumption/replenishment and associated activity records.
7. **10 simultaneous consumers competing for 3 items:** assert 3 success, 7 conflicts, final quantity 0 and exactly 3 activity entries.
8. **Forced audit insert failure:** assert stock update rolled back.
9. **PostgreSQL-specific parallel test:** same 10-person stock race **plus** 10 parallel votes by the same user (one succeeds).
10. **Idempotency retry tests:** same-key concurrent requests execute once; different payloads conflict; rollback and replay are verified.
11. **Registration, public configuration, and real-time tests:** validation, protected roles, secure public demo configuration, SSE formatting and PostgreSQL notifications.

To run the fast tests from a local Python environment:

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
```

The PostgreSQL-only integration test is skipped unless `TEST_POSTGRES_URL` is present. To run **all** tests against an isolated PostgreSQL test database, set `TEST_POSTGRES_URL` to its connection URL and run the same command. **Use a separate test database** (for example `snackoverflow_test`).

GitHub Actions `.github/workflows/ci.yml` starts a real PostgreSQL service and runs backend lint/tests (including PostgreSQL contention cases), frontend lint, optimistic UI and SSE tests, type-checking, and the production build on every push and pull request. The final check is the repository's [Actions page](https://github.com/umarakeel04/snack-overflow/actions).

### Live HTTP concurrency demonstration (after Docker startup)

To verify the **running API and PostgreSQL database**, rather than only the service function, run this in a separate terminal from the project root:

```bash
python scripts/smoke_http.py
```

This standard-library-only script creates a disposable snack with three packets, fires **10 simultaneous authenticated HTTP consume requests** (expect exactly three `200` and seven `409`), races **10 duplicate vote requests** (one `201`, nine `409`), checks member authorization, audits the inventory moves, and deletes the test snack. If the script exits successfully you can show its output in the recording. It does not delete historical audit entries, which is intentional.

## 🍿 Bonus: member sign-up

- The login screen now includes **Create an account**, with name, email, password, and password confirmation. After successful sign-up, the app returns to the sign-in form and asks the member to log in. The registration API currently returns a token for compatibility, but the UI does not store or use it.
- `POST /auth/register` accepts only `name`, `email`, and `password`. It never trusts a client-provided role; the server assigns `member` directly.
- Passwords must have 8–128 characters and contain at least one letter and one number. Passwords are stored using the existing per-user salted scrypt hashing, not plaintext. Emails are normalized to lowercase before insertion.
- The `users.email` unique constraint is the final concurrency-safe guard against duplicate accounts; conflicting sign-ups receive `409 EMAIL_ALREADY_REGISTERED`. Invalid requests use the existing `422` error contract.
- The public Railway URL is a **limited assignment demo**, not a hardened production identity service. There is no email verification, anti-bot challenge, password-reset flow, or registration rate limiting; a general public launch would require those protections and operational monitoring.
- Tests in `backend/tests/test_registration.py` cover new member creation, hashed passwords, normalized duplicate emails, validation, server-enforced roles, and admin-route rejection. Run `pytest -q` using `backend/requirements-dev.txt`.

## 🧠 Short design note: decisions, trade-offs, 100× users

**Decisions:**

1. **FastAPI + React/TypeScript + PostgreSQL** matches the team's familiar technologies. Keeping UI, API, and persistence separate makes it easy to test and change each layer.
2. **Atomic SQL UPDATE instead of app locks** works even when the server runs multiple workers or instances. Database constraints provide additional safeguards.
3. **Opaque database-backed sessions** enable instant revocation without maintaining a JWT blacklist; the trade-off is a database lookup per authenticated request.
4. **Composite primary key on votes** gives an invariant stronger than an application pre-check. The UI shows voted state from the server response.
5. **Audit log in the stock transaction** favors correctness over maximum throughput. Failed writes never leave phantom activity records.
6. **Stock changes have dedicated endpoints** (no quantity changes in PATCH) to prevent bypassing the activity trail.
7. **Derived status** avoids redundant storage. The summary endpoint aggregates directly in SQL so it cannot disagree with the list.
8. **Database-backed idempotency for consume** prevents double-decrementing stock on client retries. The request key and result are committed with the inventory update and activity event.
9. **Optimistic React overlays** make vote and consume actions feel immediate, but rollback automatically if the server rejects them; server values always win.
10. **PostgreSQL notifications + authenticated SSE** give cross-tab updates without duplicating write logic; clients refetch authoritative REST state.
11. **Railway private networking** keeps the API and PostgreSQL off the public internet while the frontend remains reviewable over HTTPS.

**Trade-offs / known limitations:**

- Schema creation with SQLAlchemy `create_all()` at startup is acceptable for a time-boxed demo. For production, use Alembic versioned migrations and deploy migrations separately.
- Session tokens reside in `sessionStorage` for demonstration. A deployment would use HttpOnly/SameSite cookies, HTTPS, CSRF safeguards, session cleanup, and a login rate limiter.
- Only restock and consume stock changes generate activity entries; new snack initial stock is part of creating the record. There is no edit/delete activity event (not required by the challenge).
- The weekly winner is based on the preceding 7×24 hours, not a Monday–Sunday calendar window. A vote cast before that window is not counted; changing this definition would require product input.
- The app **does implement authenticated SSE** and has a **public Railway demo**; it does not yet have full automated end-to-end browser tests or production-grade availability/observability. SSE requires a persistent connection and reconnect logic; cross-instance fanout depends on PostgreSQL notifications.
- Consume idempotency receipts do not yet have a cleanup policy; a production system should define a retention window and background cleanup.
- The public sign-up flow has no email verification, password reset, rate limiting or bot protection. The Railway trial is usage-limited, so the demo may not remain online indefinitely.

**What breaks first at 100× users?**

- Repeated per-request SQL aggregation for vote totals, weekly winner, and dashboard summary, plus a DB lookup for every session. Profile these queries first; use the included `votes(snack_id, created_at)` index, then add targeted caching with careful invalidation, and connection pooling.
- Hot snack rows experience increased row-lock contention. The conditional UPDATE remains correct, but latency rises on very popular snacks. Measure conflict rates, DB lock waits, p95 latency, and consider a queue for extremely hot items if product requirements justify it.
- A single small PostgreSQL instance becomes the capacity bottleneck. Scale reads where appropriate, handle migrations, centralize metrics/tracing, add backups, and use managed database resources.
- Thousands of persistent SSE connections increase backend memory, connection and reconnection load. Consider a dedicated event gateway or managed pub/sub for high-volume fanout; continue to treat the database and REST endpoints as authoritative.

**Why this order of implementation?** The assignment says depth beats breadth. The central proof is *3 successful consumes, 7 conflicts, no negative stock, and 3 activity entries* under a real database race. Sign-up, idempotency, optimistic UI, live updates and deployment came after the atomic stock, vote uniqueness, authentication and CI checks were working. These bonuses improve usability and reviewability, but do not replace the core correctness guarantees.

For the implementation steps and demo script, see [`docs/IDEMPOTENCY_BONUS_GUIDE.md`](docs/IDEMPOTENCY_BONUS_GUIDE.md).

### Optimistic frontend updates (bonus)

Vote/Unvote and Consume update the **visible snack card immediately** without waiting for the network response. `frontend/src/optimistic.ts` supplies pure, non-mutating previews; `Dashboard` holds per-snack overlays on top of the last confirmed API page. The affected card is temporarily locked while the request is pending, preventing overlapping vote/consume operations on the same snack.

- **Success:** The API response becomes the confirmed cached snack; the UI re-fetches the page and summary to reconcile server-side sort, filters, stock statuses, and Snack of the Week. The preview is then removed.
- **Failure/409/offline:** The preview is removed (rollback to the latest available server snapshot), an error notification is shown, and the list is re-fetched. The server remains authoritative; no optimistic state is written to PostgreSQL.
- **Stale reads:** Keeping previews in separate overlays stops unrelated in-flight GET requests from overwriting the temporary display or causing a stale-snapshot rollback.
- **Consume retries:** The dialog retains the same `Idempotency-Key` for retries of the same amount; changing the amount gets a new key, so the server still protects against double-consumption.

The summary cards and weekly leader remain server-authoritative and refresh **after confirmation**; we intentionally do not fabricate those aggregated totals during a pending request. **SSE additionally refreshes other open tabs** after committed changes. Run the standalone projection tests with **Node.js 22+**: `cd frontend && npm run test:optimistic`. See [`docs/OPTIMISTIC_UI_GUIDE.md`](docs/OPTIMISTIC_UI_GUIDE.md) for manual failure/rollback verification.

## 🔴 Real-time pantry updates (bonus)

PostgreSQL `LISTEN/NOTIFY` now pushes invalidation events to authenticated Server-Sent Events clients at `GET /snacks/events`. The backend seed installs statement-level triggers on `snacks` and `votes` during startup. Notifications arrive **after commit**, so rolled-back changes never appear. The React dashboard refreshes snack counts, the weekly winner, and activity history automatically across open tabs, while preserving pending optimistic UI overlays. The UI shows **Live sync** when connected and reconnects automatically after interruptions.

This uses a streaming `fetch` with the existing Bearer token in the request **header**, never in a URL. Nginx disables buffering for the SSE endpoint. Test with two tabs (vote or consume in one, watch the other without pressing Refresh). See [`docs/REALTIME_BONUS_GUIDE.md`](docs/REALTIME_BONUS_GUIDE.md) for verification, limitations and 100× scaling trade-offs.


## ☁️ Public deployment (live demo bonus)

**Public URL:** https://frontend-production-03621756.up.railway.app/

The Railway deployment uses **private** PostgreSQL and FastAPI services plus a **public** Nginx/React frontend. Nginx proxies `/api` and authenticated `/api/snacks/events` to the internal backend. Hosted credentials are configured privately as Railway variables (`PUBLIC_DEMO_MODE`, `DEMO_ADMIN_EMAIL`, `DEMO_ADMIN_PASSWORD`, `DEMO_MEMBER_EMAIL`, `DEMO_MEMBER_PASSWORD`); local demo passwords must not be used in public hosting. The backend's seed creates accounts only when missing, so changing an environment password does **not** automatically reset an existing user's database password hash.

**Reviewer access:** Admin/member sign-in details are sent privately with the submission. Public sign-up is restricted to the **member** role. Do not add Railway variable values or credentials to the repository.

The hosted demo depends on Railway trial resources and may become unavailable after the trial credit or usage allowance is exhausted. See [`docs/RAILWAY_DEPLOYMENT_GUIDE.md`](docs/RAILWAY_DEPLOYMENT_GUIDE.md) for deployment, limitations and testing.

## 📂 Project structure

```text
snack-overflow/
├── .github/workflows/ci.yml
├── .env.example
├── docker-compose.yml
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Login, dashboard, role-aware controls, activity, dialogs
│   │   ├── api.ts           # Typed API client and unified errors
│   │   ├── optimistic.ts    # Optimistic stock/vote previews and rollback overlays
│   │   ├── realtime.ts      # Authenticated SSE subscription and reconnect logic
│   │   ├── types.ts         # API response and input types
│   │   └── styles.css       # Responsive styling
│   ├── tests/
│   │   ├── optimistic.test.mjs   # Optimistic UI projection tests
│   │   └── realtime.test.mjs     # SSE parser tests
│   ├── Dockerfile
│   ├── nginx.conf.template  # Nginx API + SSE proxy (local and Railway)
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── main.py          # Routes, filters, auth guards, errors
│   │   ├── services.py      # Atomic inventory and audit transactions
│   │   ├── idempotency.py   # DB-backed consume idempotency and response replay
│   │   ├── realtime.py      # PostgreSQL LISTEN/NOTIFY and SSE helpers
│   │   ├── models.py        # SQLAlchemy tables and constraints
│   │   ├── security.py      # Scrypt passwords + sessions + role dependency
│   │   ├── schemas.py       # Pydantic validation and API contract
│   │   ├── seed.py          # Repeatable demo data
│   │   ├── database.py      # DB connections and sessions
│   │   └── config.py        # Environment-based settings
│   ├── tests/
│   │   ├── test_api.py
│   │   ├── test_concurrency.py
│   │   ├── test_registration.py
│   │   ├── test_idempotency.py
│   │   ├── test_realtime.py
│   │   └── test_public_deployment.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── Dockerfile
├── scripts/
│   ├── smoke_http.py          # Live 10-request HTTP race and permissions smoke test
│   └── smoke_idempotency.py   # Live 10 same-key retries and replay smoke test
└── docs/
    ├── DEMO_AND_SUBMISSION.md
    ├── SIGNUP_BONUS_GUIDE.md
    ├── IDEMPOTENCY_BONUS_GUIDE.md
    ├── OPTIMISTIC_UI_GUIDE.md
    ├── REALTIME_BONUS_GUIDE.md
    └── RAILWAY_DEPLOYMENT_GUIDE.md
```

## ✉️ Submission

Submit to `torsha@bipolarfactory.com` with subject `Round 2 – Full Stack Intern – Umar Akeel V M` by **Monday, 16 November 2026, 11:00 AM IST** (as confirmed in the recruitment email). Include:

- Link to a **public GitHub repository** with meaningful commit history.
- This README, including local setup instructions, API details, concurrency and authorization approach, and design note.
- **Your own 3–5 minute screen recording**, demonstrating both accounts, common actions, error handling, and the crucial atomic SQL/test code.
- The [live Railway demo](https://frontend-production-03621756.up.railway.app/) and **private reviewer credentials** for the hosted Admin and Member accounts (not in GitHub or the recording).

See `docs/DEMO_AND_SUBMISSION.md` for a concrete submission checklist and recording outline.

---

*Built as an engineering assignment. The most important feature is not how many packets appear in the UI; it is that the database never tells two people the same last packet belongs to them.*
