import test from 'node:test';
import assert from 'node:assert/strict';
import { parseSseFrames } from '../src/realtime.ts';

test('parses a connected frame and a change frame in the same chunk', () => {
  const data = 'event: connected\ndata: {}\n\nevent: change\ndata: {"table":"votes"}\n\n';
  assert.deepEqual(parseSseFrames(data), { events: ['connected', 'change'], remaining: '' });
});

test('retains partial frames split across network chunks', () => {
  const first = parseSseFrames('event: chan');
  assert.deepEqual(first.events, []);
  const second = parseSseFrames(first.remaining + 'ge\ndata: {}\n\n');
  assert.deepEqual(second.events, ['change']);
  assert.equal(second.remaining, '');
});

test('ignores keepalive comments and unexpected event names', () => {
  const chunk = ': keepalive\n\nevent: odd\ndata: 1\n\nevent: change\ndata: 2\n\n';
  assert.deepEqual(parseSseFrames(chunk).events, ['change']);
});

test('supports CRLF SSE framing', () => {
  const result = parseSseFrames('event: change\r\ndata: {}\r\n\r\n');
  assert.deepEqual(result, { events: ['change'], remaining: '' });
});
