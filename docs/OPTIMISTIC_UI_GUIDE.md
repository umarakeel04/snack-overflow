# Bonus: Optimistic Vote and Consume (with rollback)

This patch **does not change the FastAPI API or database rules**. It only makes the React interface more responsive while maintaining the backend as the authority.

## How it works

- `frontend/src/optimistic.ts` implements pure preview functions for votes and stock and composes pending snack overlays with a server-fetched list.
- `frontend/src/App.tsx` shows the preview at the moment the user submits the action. The affected snack's action buttons are disabled while in flight.
- A confirmed API response updates the cached snack before the preview is removed. A subsequent fetch reconciles filters, sorting, overall stock counts and Snack of the Week.
- For any network/server error, including a stock conflict (`409`), the overlay is removed so the original/most recent server snapshot becomes visible. A fresh fetch reconciles potentially changed server data.
- When a response arrives for a different snack or a background reload completes, the pending overlay keeps the current preview visible. Multiple different snacks can have independent pending operations.
- The existing consume dialog's `Idempotency-Key` is preserved on retry for the same amount, so an ambiguous response cannot cause the stock to be deducted twice.

## Install & run (PowerShell, project root)

```powershell
npm --prefix frontend run test:optimistic  # requires Node.js 22+
npm --prefix frontend run lint
npm --prefix frontend run build
docker compose up -d --build frontend
```

The existing API and PostgreSQL containers do **not** need to be rebuilt. No schema migration is required.

## Manual acceptance tests

1. **Successful vote:** Sign in as a member. Under Chrome DevTools → Network, enable a slower network throttle. Click the empty heart next to a snack. The heart fills and vote count increases *before* the response finishes; other actions on that snack are temporarily disabled. The final count matches the server after confirmation.
2. **Vote rollback:** Return to normal networking, load the dashboard, then switch DevTools Network to **Offline**. Click Vote/Unvote. The icon/count updates immediately and then returns to its original value when the API rejects the request; an error toast appears. Switch back Online and click Refresh. **Do not log out while offline.**
3. **Successful consume:** Choose a snack with more than two packets, click Consume, enter 1 and Confirm. The card's quantity decreases immediately, and the stock label changes at the threshold. The server result eventually confirms the count.
4. **Consume rollback:** With the dashboard already loaded, switch DevTools Network to Offline, open Consume and Confirm. The provisional quantity drops, then returns to the original value after the network error. The consume dialog remains open and displays an error. Switch Online and refresh.
5. **Server conflict:** In two browser sessions, open the same last packet. Consume from one session first, then confirm in the other. The second client receives `409` and updates to the server's current quantity. The UI must never display a negative number.
6. **Regression:** Confirm member/admin authorization, sign-up, vote uniqueness and the live smoke tests remain valid (`python scripts/smoke_http.py` and `python scripts/smoke_idempotency.py`).

## Known trade-offs

- The optimistic preview applies to the **currently visible snack card**, not aggregated dashboard summary or weekly winner. Those remain server-authoritative until the next successful GET.
- A pending card may temporarily remain in a search/filter/sort position that no longer matches its new stock or vote number. The next API refresh resolves that difference.
- A network failure after the server already committed a consume can temporarily show old data. The automatic refresh and idempotent retry reconcile this safely; only the backend decides the true stock quantity.
- Node's built-in TypeScript stripping is used for four pure helper tests (Node 22+); CI uses Node 22. We did not introduce a heavyweight browser-testing dependency during this assignment.
