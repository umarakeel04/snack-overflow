# Demo, interview preparation and submission guide

**Confirmed email deadline:** Monday, 16 November 2026 at **11:00 AM IST**. The PDF mistakenly shows Saturday, 14 November; follow the email confirmation.

## 1. Local first-run checklist

- [ ] Install Docker Desktop (Windows: ensure WSL2/Docker Desktop engine is running).
- [ ] Extract this repository or clone it from GitHub, then open a terminal in the project root.
- [ ] Copy `.env.example` to `.env` (PowerShell: `Copy-Item .env.example .env`). Replace the sample PostgreSQL password with your own simple local password (letters/numbers recommended for the DSN).
- [ ] Run `docker compose up --build` and check that all 3 services (db, backend, frontend) start successfully.
- [ ] Open http://localhost:3000 and test both demo credentials.
- [ ] Open http://localhost:8000/docs and find the REST routes.
- [ ] In a separate terminal from the project root, run `python scripts/smoke_http.py`. It should print `PASS` and the expected **3 successful, 7 rejected** simultaneous HTTP requests.
- [ ] If the frontend displays a network error: check `docker compose logs backend`, `docker compose logs frontend`, and `docker compose ps`.
- [ ] If Docker is not available: follow README's Python/Node/PostgreSQL manual setup.

## 2. Demo flow (3–5 minute recording, suggested script)

**0:00–0:30 — Show the goal and architecture.**

> This is Snack Overflow, an office snack tracker. I used React with TypeScript for the frontend, FastAPI for the REST backend, and PostgreSQL for data integrity. The main challenge was ensuring stock cannot go negative under simultaneous consumption.

**0:30–1:25 — Member journey.**

1. Choose the Member demo account and sign in.
2. Show status counters, Snack of the Week, search, category/status filters, and pagination.
3. Vote once, show updated count, then click to remove the vote.
4. Consume one packet of Masala Peanuts and show the new stock.
5. Try consuming more than remaining stock (or consume until gone) and show the clear `409` message.
6. Mention that the Member has no add/restock/edit/delete controls; restrictions are also enforced on the API.

**1:25–2:20 — Admin journey.**

1. Log out and sign in as Admin.
2. Add a new snack, restock it, edit category/threshold, and optionally delete it.
3. Open Activity history, show who restocked/consumed, when, and how much.
4. Try filtering by `running_low`, then `gone`.

**2:20–3:50 — Strongest engineering proof (most important).**

1. Open `backend/app/services.py`.
2. Point to `UPDATE snacks SET quantity = quantity - amount WHERE id = ... AND quantity >= amount RETURNING name`.
3. Explain: database row locking and rechecking the condition ensure 3 wins out of 10 on 3 remaining; losers get `409`.
4. Point out the activity insert and stock update are committed in one transaction.
5. Open `backend/app/models.py` and show the `(user_id, snack_id)` vote primary key and quantity `CHECK` constraint.
6. Show `python scripts/smoke_http.py` passing against the live Docker application. Also demonstrate the `backend` Pytest suite or the GitHub Actions run including PostgreSQL.

**3:50–4:40 — Explain decisions and trade-offs.**

> I prioritized database correctness, server-side permissions, and tests over optional real-time updates. Passwords use salted scrypt hashes, sessions are revocable, and the API has consistent error responses. At 100 times the usage, I would optimize aggregate read queries and session lookups, add proper migrations and production-grade cookie auth, and monitor database contention.

**4:40–5:00 — Close.**

> Thank you for reviewing my assignment. I can explain my code and extend the API or UI in the next round.

Use OBS Studio, Windows Snipping Tool's screen recorder, or any recorder that captures both app and code. Ensure microphone audio is clear; aim at 3–5 minutes. Save an MP4 file or share a viewable recording link.

## 3. Push the repository to GitHub

1. Create a **new empty public** GitHub repository named `snack-overflow`. Do **not** initialize it with a README/license/.gitignore, because this project already has its own Git history.
2. From the extracted project root, open a terminal.
3. Check the history:

```bash
git log --oneline --max-count=8
git status
git remote -v
```

4. Add the real URL of the GitHub repository you just created and push:

```bash
git remote add origin https://github.com/YOUR-USERNAME/snack-overflow.git
git branch -M main
git push -u origin main
```

5. Verify all files and several meaningful commits are visible on GitHub.
6. Click the **Actions** tab. The workflow runs backend tests (including PostgreSQL contention) and the React TypeScript build. If anything fails, fix it and push again—do not submit with a known failing check.
7. Check the repo's Files tab and confirm that there is **no `.env`**, no real API token, and no real production password.

If you downloaded a version of the code **without** the `.git` directory, initialize with `git init`, make separate commits for backend, UI, tests, and documentation, then push. Do not falsely claim a tested feature or invent a commit history.

## 4. Pre-submission quality checklist

- [ ] `docker compose up --build` works from a clean setup.
- [ ] Can log in as both Member and Admin.
- [ ] Member cannot add/edit/delete/restock via **HTTP API**, not just UI.
- [ ] `python scripts/smoke_http.py` reports 3 successes / 7 conflicts, one accepted vote / nine conflicts, a protected admin route and consistent audit entries.
- [ ] Duplicate votes fail at the database unique constraint.
- [ ] Invalid quantities produce consistent `422`; no negative stock.
- [ ] Loading, error, empty, and small-screen states have been checked.
- [ ] GitHub Actions has succeeded, including the Postgres integration test.
- [ ] README has working setup, demo accounts, API docs, schema, design note, and scaling tradeoffs.
- [ ] A real 3–5 minute screen recording exists and can be viewed.
- [ ] Send well **before** 11:00 AM IST Monday, 16 Nov.

## 5. Submission email template

**To:** torsha@bipolarfactory.com  
**Subject:** Round 2 – Full Stack Intern – Umar Akeel V M

Dear Torsha,

Thank you for the opportunity to take part in Round 2 of the Full Stack Intern selection process.

I have completed the Snack Overflow assignment, focusing on concurrency-safe inventory updates, database-enforced vote uniqueness, secure role-based authorization, and automated testing. I also implemented a responsive dashboard and documented the design decisions and trade-offs.

GitHub repository: **[INSERT YOUR ACTUAL PUBLIC REPO LINK]**  
Screen recording (3–5 minutes): **[INSERT WORKING VIDEO LINK OR ATTACH MP4]**  
Live demo (optional): **[INSERT LIVE URL IF AVAILABLE]**

The README contains setup instructions, demo credentials, API endpoints, schema details, and explanations of the concurrency handling and authorization approach.

Thank you for reviewing my submission. I look forward to discussing the implementation in the next round.

Best regards,  
Umar Akeel V M

## 6. Five questions you should be able to answer

**Q1: Why is a read-before-write stock check wrong?**  
Two requests could both read quantity = 1 before updating it, leading to lost updates or multiple successes for the same packet. The DB conditional `UPDATE` is evaluated under a row lock, so only one update can succeed when one packet remains.

**Q2: Why must the activity insert use the same transaction?**  
If inventory decreases but the activity insert fails separately, the audit trail becomes incorrect. A single commit succeeds or fails for both writes.

**Q3: What happens if an ordinary member calls the admin REST endpoint directly?**  
`admin_only` checks their user role on the server, independent of whether the frontend hides the button. They get HTTP `403`.

**Q4: Why doesn't a prior `SELECT` stop duplicate votes?**  
Two requests can both see "no vote" before either inserts. The database `(user_id, snack_id)` composite primary key makes the duplicate impossible even under concurrency.

**Q5: Why FastAPI/React/PostgreSQL rather than Firebase?**  
This task explicitly requires your own backend API and relational database constraints. FastAPI makes typed validation and API design easy to demonstrate, React is good for an interactive dashboard, and PostgreSQL gives robust transactions, row locking, and unique constraints.
