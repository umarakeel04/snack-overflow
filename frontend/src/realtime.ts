/** Authenticated Server-Sent Events using fetch instead of EventSource.
 * EventSource cannot attach the app's Authorization: Bearer header.
 */
export type PantryEvent = 'connected' | 'change';

/** Consume complete SSE frames, keeping a possibly incomplete trailing frame. */
export function parseSseFrames(chunk: string): { events: PantryEvent[]; remaining: string } {
  let remaining = chunk.replace(/\r\n/g, '\n');
  const events: PantryEvent[] = [];
  for (;;) {
    const boundary = remaining.indexOf('\n\n');
    if (boundary === -1) break;
    const frame = remaining.slice(0, boundary);
    remaining = remaining.slice(boundary + 2);
    const eventLine = frame.split('\n').find(line => line.startsWith('event:'));
    const event = eventLine?.slice(6).trim();
    if (event === 'change' || event === 'connected') events.push(event);
  }
  return { events, remaining };
}

function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise(resolve => {
    if (signal.aborted) { resolve(); return; }
    const finish = () => { clearTimeout(timer); signal.removeEventListener('abort', finish); resolve(); };
    const timer = window.setTimeout(finish, ms);
    signal.addEventListener('abort', finish, { once: true });
  });
}

/** Subscribe until the returned cleanup function is called.
 * Reconnect on stream/network failure. Every event is an invalidation hint;
 * the existing REST endpoints remain the source of truth.
 */
export function subscribePantry(token: string, onChange: () => void, onStatus?: (connected: boolean) => void): () => void {
  const controller = new AbortController();
  const base = import.meta.env.VITE_API_BASE_URL || '/api';
  void (async () => {
    let retryMs = 1000;
    while (!controller.signal.aborted) {
      try {
        const response = await fetch(`${base}/snacks/events`, {
          headers: { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' },
          signal: controller.signal,
          cache: 'no-store',
        });
        // Do not endlessly reconnect if authentication has expired.
        if (response.status === 401 || response.status === 403) { onStatus?.(false); return; }
        if (!response.ok || !response.body) throw new Error('SSE unavailable');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        retryMs = 1000;
        try {
          while (!controller.signal.aborted) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const parsed = parseSseFrames(buffer);
            buffer = parsed.remaining;
            for (const event of parsed.events) {
              if (controller.signal.aborted) break;
              if (event === 'connected') onStatus?.(true);
              onChange();
            }
          }
        } finally {
          await reader.cancel().catch(() => undefined);
        }
      } catch {
        // Closing a tab aborts the fetch. Other failures trigger a retry.
      }
      if (!controller.signal.aborted) {
        onStatus?.(false);
        await pause(retryMs, controller.signal);
        retryMs = Math.min(retryMs * 2, 15000);
      }
    }
  })();
  return () => controller.abort();
}
