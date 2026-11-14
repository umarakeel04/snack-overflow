import test from 'node:test';
import assert from 'node:assert/strict';
import { previewVote, previewConsume, statusFor, withOptimisticSnacks } from '../src/optimistic.ts';

const sample = Object.freeze({
  id: 11, name: 'Demo peanuts', category: 'savoury', quantity: 3,
  low_stock_threshold: 2, status: 'stocked', votes: 2, has_voted: false,
});

test('vote and unvote are immediate projections without mutating source', () => {
  const voted = previewVote(sample);
  assert.equal(voted.has_voted, true);
  assert.equal(voted.votes, 3);
  assert.equal(previewVote(voted).has_voted, false);
  assert.equal(previewVote(voted).votes, 2);
  assert.equal(sample.votes, 2);
});

test('optimistic consumption updates quantity and derived status', () => {
  const almostGone = previewConsume(sample, 2);
  assert.equal(almostGone.quantity, 1);
  assert.equal(almostGone.status, 'running_low');
  const gone = previewConsume(sample, 3);
  assert.equal(gone.quantity, 0);
  assert.equal(gone.status, 'gone');
  assert.equal(sample.quantity, 3);
  assert.equal(previewConsume(sample, 99).quantity, 0);
  assert.equal(statusFor(1, 0), 'stocked');
});

test('pending preview survives a server refresh and clears without stale rollback', () => {
  const page = { items: [sample], total: 1, page: 1, page_size: 8, pages: 1 };
  const voted = previewVote(sample);
  const pending = new Map([[sample.id, voted]]);
  assert.equal(withOptimisticSnacks(page, pending)?.items[0].votes, 3);
  const refreshed = { ...page, items: [{ ...sample, votes: 5 }] };
  assert.equal(withOptimisticSnacks(refreshed, pending)?.items[0].votes, 3);
  assert.equal(withOptimisticSnacks(refreshed, new Map())?.items[0].votes, 5);
  assert.equal(page.items[0].votes, 2);
});

test('two independent pending snacks do not overwrite one another', () => {
  const other = { ...sample, id: 12, votes: 0 };
  const page = { items: [sample, other], total: 2, page: 1, page_size: 8, pages: 1 };
  const overlays = new Map([[11, previewConsume(sample, 1)], [12, previewVote(other)]]);
  const viewed = withOptimisticSnacks(page, overlays);
  assert.equal(viewed?.items[0].quantity, 2);
  assert.equal(viewed?.items[1].votes, 1);
  overlays.delete(11);
  assert.equal(withOptimisticSnacks(page, overlays)?.items[0].quantity, 3);
  assert.equal(withOptimisticSnacks(page, overlays)?.items[1].votes, 1);
});
