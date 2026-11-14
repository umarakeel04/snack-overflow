/** UI-only projections. PostgreSQL remains the authority for every mutation. */
import type { Snack, SnackPage, StockStatus } from './types';

export function statusFor(quantity: number, threshold: number): StockStatus {
  if (quantity === 0) return 'gone';
  return quantity <= threshold ? 'running_low' : 'stocked';
}

export function previewVote(snack: Snack): Snack {
  const hasVoted = !snack.has_voted;
  return {
    ...snack,
    has_voted: hasVoted,
    votes: Math.max(0, snack.votes + (hasVoted ? 1 : -1)),
  };
}

export function previewConsume(snack: Snack, amount: number): Snack {
  // Do not display impossible negative stock. The API still validates the
  // request, including retries whose original request may already have run.
  if (!Number.isInteger(amount) || amount < 1) return snack;
  const quantity = Math.max(0, snack.quantity - amount);
  return { ...snack, quantity, status: statusFor(quantity, snack.low_stock_threshold) };
}

/**
 * Apply transient overlays to the latest server page without mutating it.
 * While a request is pending, the overlay survives unrelated re-fetches;
 * removing it immediately restores the latest available server snapshot.
 */
export function withOptimisticSnacks(
  page: SnackPage | null,
  pending: ReadonlyMap<number, Snack>,
): SnackPage | null {
  if (!page || pending.size === 0) return page;
  return {
    ...page,
    items: page.items.map(snack => pending.get(snack.id) ?? snack),
  };
}
