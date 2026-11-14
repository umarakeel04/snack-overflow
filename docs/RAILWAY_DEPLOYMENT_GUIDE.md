# Snack Overflow — Railway live deployment (bonus)

The application needs **three Railway services in one project/environment**:

1. `Postgres` — Railway PostgreSQL database template (private)
2. `backend` — this repository, root directory `/backend` (private, **no public domain**)
3. `frontend` — this repository, root directory `/frontend` (only public service; target port **80**)

**Before deployment:** local `git status`, tests and smoke checks should be clean/passing. Commit these patch files to `main` so Railway can build them from GitHub. Verify GitHub Actions passes.

## Important: account safety

The local seeded login buttons and passwords are development-only. Public hosting **must not** seed `Admin123!` or `Member123!`. The patch allows private per-deployment credentials using environment variables. The React production build hides the local demo login shortcuts when `VITE_PUBLIC_DEPLOYMENT=true`.

Do not paste credentials or database URLs into public GitHub, screenshots, or the screen recording. Share reviewer credentials privately in the assignment submission email. Use a disposable demo database. Public sign-up has no email verification/rate limit; this is a demonstration, **not** a hardened multi-tenant production service. Turn off the deployment when the review ends if you don't need it.

## 1. Create project and database

- Sign in to https://railway.com/ with GitHub.
- Create a New Project and add **PostgreSQL** from the template. Name the database service `Postgres` (or adjust the references below).
- Do not enable a public TCP proxy for Postgres.
- Railway prices/credits and limits vary by plan. Review them before proceeding.

## 2. Add private backend service

- Click **New** > **GitHub Repo**, select `umarakeel04/snack-overflow`, name the service `backend`.
- Settings > Source > **Root Directory**: `/backend`.
- Keep the Dockerfile build. No need to change the Dockerfile.
- Under **Variables**, add each of these:

| Variable | Value |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `PUBLIC_DEMO_MODE` | `true` |
| `DEMO_ADMIN_EMAIL` | An email you choose for reviewer admin (e.g. admin@snackoverflow.dev) |
| `DEMO_ADMIN_PASSWORD` | A unique, random password of 12+ characters (NOT `Admin123!`) |
| `DEMO_MEMBER_EMAIL` | A different email you choose for reviewer member |
| `DEMO_MEMBER_PASSWORD` | A different strong password of 12+ characters (NOT `Member123!`) |

When entered in Railway's GUI, `${{Postgres.DATABASE_URL}}` is a reference to the database service's URL. The backend converts `postgresql://...` into SQLAlchemy's psycopg dialect automatically.

- Make sure `backend` has a private domain (`backend.railway.internal` in new projects).
- **Do not generate a public domain for backend.** `uvicorn` listens on port `8000` on all interfaces.
- Deploy. Startup runs `python -m app.seed`; logs should contain `Snack Overflow demo seed ready...`.

## 3. Add public frontend service

- Click **New** > **GitHub Repo**, select the same repo again, name this service `frontend`.
- Settings > Source > **Root Directory**: `/frontend`.
- In **Variables**:

| Variable | Value |
|---|---|
| `API_UPSTREAM` | `http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:8000` |
| `VITE_PUBLIC_DEPLOYMENT` | `true` |

Set these values **before triggering a fresh frontend build**. `API_UPSTREAM` is a server-side Nginx setting; the internal DNS name must never be fetched directly by the browser. The official Nginx entrypoint expands only this one variable into its server config; the REST endpoints stay under `/api`, and SSE under `/api/snacks/events`.

- Deploy. The frontend Docker image serves Nginx on **port 80**. Railway > frontend > Settings > Networking > **Generate Domain**, selecting target port **80** if asked.
- Open the HTTPS URL Railway actually assigns. Do not invent/share a URL before Railway generates it.

## 4. Test the hosted site

- Open `https://<your-railway-domain>/api/health` — expect `{"status":"ok"}` (if not, Nginx-to-backend networking needs correction).
- Open the root site in two separate browser sessions, login with the **private credentials** set above; inspect member/admin role controls.
- Validate creation, stock consumption, restocking, vote/unvote, duplicate-vote rejection, search/sorting, history, and Sign-Up.
- In two tabs, look for `● Live sync` and verify voting/restock updates propagate.
- Test at least one concurrent case locally: the existing real Postgres tests are already included in GitHub Actions. The hosted DB is new and need not be populated with local test data.
- Verify the browser DevTools Network has no HTTP 5xx and the `/api/snacks/events` request stays open with SSE frames.

## 5. Troubleshooting

| Problem | Check |
|---|---|
| API returns 502 from frontend | Backend deployed/running; `API_UPSTREAM` references `backend.RAILWAY_PRIVATE_DOMAIN`, private DNS and port 8000; frontend redeployed after setting variable |
| Backend fails to start | Backend service Logs; `DATABASE_URL` correctly references Postgres; database service healthy; `PUBLIC_DEMO_MODE` requires four demo account variables |
| Public site displays Nginx 502 | Nginx generated upstream incorrectly; check frontend Deploy Logs and service variables (no credentials in logs) |
| Public URL opens but 404 | Frontend Root Directory must be `/frontend`; domain target port 80 |
| Live sync says Connecting | Check SSE `/api/snacks/events` streaming (not buffered), Postgres LISTEN/NOTIFY trigger installed at backend startup |
| Login fails using local buttons | Expected: public build hides local-only buttons and public credentials differ from local demo |
| Site not reachable | Check the service deployment state, target port, generated domain and Railway usage/quota |

## Cost and submission

Railway has a time/credit-limited trial and plans with resource-based usage. Double-check current prices and service availability. A running frontend + backend + PostgreSQL may exceed small free credits, so monitor usage and stop/delete after review if needed.

In the submission email, include the actual Railway HTTPS link and the GitHub repo link. Share hosted reviewer member/admin credentials privately; do not commit them. Record your screen demo before the deadline, regardless of hosting status.
