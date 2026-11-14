# Bonus: real-time updates using PostgreSQL notifications + Server-Sent Events

## What changes

- Every committed insert/update/delete to `snacks` or `votes` emits a PostgreSQL `NOTIFY` via statement-level triggers.
- `GET /snacks/events` opens an **authenticated** SSE stream (`Authorization: Bearer …`).
- The browser uses streaming `fetch` rather than `EventSource`, because native `EventSource` cannot attach the existing Bearer header. Tokens never go into URL query parameters.
- The stream carries only an invalidation hint (`table`, `operation`), **not** user names, tokens, or private data. Upon a hint, React fetches the current snack page and summary through the existing authenticated REST endpoints. The admin Activity page also refreshes.
- Two browsers, tabs, or backend workers receive the same PostgreSQL notifications. Nginx has buffering disabled for this endpoint.
- A `connected` event triggers a reload after `LISTEN` is active, preventing an initial subscribe/read gap. Disconnects cause exponential reconnects. A reconnection refreshes the current page.
- Optimistic UI overlays remain in place until their own requests settle. Background invalidations cannot overwrite them.
- PostgreSQL only emits transaction notifications **on commit**. A failed audit insert or transaction rollback produces no phantom event; a replayed idempotency request does not create a second stock or notification update.

## Install and start

Apply the patch to the *current* repository (after the Optimistic UI update). From the repository root:

```powershell
docker compose up -d --build backend frontend
```

The backend startup seed installs/reinstalls the PostgreSQL triggers. It does **not** drop tables or reset pantry data. Do not use `docker compose down -v`.

Visit `http://localhost:3000` and log in. The top bar should show `● Live sync` when the SSE connection is established. `◌ Connecting…` indicates disconnected/retrying. A continuously disconnected state should be investigated using `docker compose logs --tail=100 backend` and Chrome's Network tab (the `/api/snacks/events` request should be **pending**, not repeatedly failing).

## Manual two-tab verification

1. Open **two separate tabs** on `http://localhost:3000` (you can use two different demo accounts or two tabs with the same account).
2. Keep both tabs visible side by side; verify both say **Live sync**. No Refresh button is required.
3. Vote or unvote in Tab A. The vote count should update in Tab B automatically.
4. Consume 1 packet in Tab A. The quantity and derived status update in Tab B automatically. Admin restock works the same way.
5. On the admin account, open **Activity history** in Tab B. Consume/restock in Tab A and confirm the history updates.
6. Try the original concurrency/idempotency smoke tests; they must still pass.
7. Stop backend and then restart it. The indicator should show reconnecting, then return to Live sync. After reconnect it should refresh stock.

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run test:realtime
npm run test:optimistic
npm run lint
npm run build
cd ..
python scripts/smoke_http.py
python scripts/smoke_idempotency.py
```

Locally, the PostgreSQL integration tests skip unless `TEST_POSTGRES_URL` points at a *separate dedicated test database*. GitHub Actions supplies a PostgreSQL service and runs these tests. The new PostgreSQL test checks a notification after commit, no notification after rollback, and trigger installation on repeated starts.

## Architecture and tradeoffs

```
Tab A -> API -> PostgreSQL commit -> statement trigger -> NOTIFY
                                       |                 |
                           API instance #1 LISTEN      API instance #2 LISTEN
                                  |                         |
                                 SSE                       SSE
                                  |                         |
                               Tab B REST refresh        Other tabs
```

PostgreSQL notifications are transient invalidation signals, **not a durable event log**. The REST API remains authoritative, and reconnecting reloads current state. Each browser connection currently uses one dedicated PostgreSQL `LISTEN` connection. This is fine for an office-sized demonstration but would exhaust database connections at 100× users; production should use one LISTEN subscriber per API process (or Redis/pub-sub/message broker) and broadcast to bounded per-client queues. Stream session expiry/revocation should be periodically revalidated at scale. Rate limiting, jitter and monitoring would be added for public deployment.
