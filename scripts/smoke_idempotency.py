"""Verify idempotent consume against the LIVE Docker API (Python standard library).

Run from project root: python scripts/smoke_idempotency.py
Creates a disposable snack and deletes it afterwards. Intended for local demo only.
"""
import json
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlsplit

BASE = os.getenv('SNACK_API_URL', 'http://localhost:8000').rstrip('/')


def api(method, path, token=None, payload=None, request_key=None):
    """Send directly to the local API, bypassing Windows/system HTTP proxies.

    An HTTP proxy or gateway can remove custom headers, which makes every
    retry look like a new consume request. http.client uses a direct socket.
    """
    parsed = urlsplit(BASE)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"Invalid SNACK_API_URL: {BASE}")
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if request_key is not None:
        headers["Idempotency-Key"] = request_key
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    conn_type = HTTPSConnection if parsed.scheme == "https" else HTTPConnection
    connection = conn_type(parsed.hostname, parsed.port, timeout=40)
    full_path = parsed.path.rstrip("/") + path
    if not full_path.startswith("/"):
        full_path = "/" + full_path
    try:
        connection.request(method, full_path, body=data, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        return response.status, json.loads(raw) if raw else None
    finally:
        connection.close()


def main():
    status, admin = api('POST', '/auth/login', payload={
        'email': 'admin@snackoverflow.dev', 'password': 'Admin123!'})
    assert status == 200, f'Admin login failed: {status}, {admin}'
    status, member = api('POST', '/auth/login', payload={
        'email': 'member@snackoverflow.dev', 'password': 'Member123!'})
    assert status == 200, f'Member login failed: {status}, {member}'
    admin_token, member_token = admin['token'], member['token']
    # A deliberately invalid header on a nonexistent snack MUST trigger 422
    # before snack lookup. 404 means the header never reached the API.
    probe_code, probe_body = api('POST', '/snacks/999999999/consume',
                                 member_token, {'amount': 1}, 'short')
    assert (probe_code == 422 and probe_body.get('error', {}).get('code') == 'INVALID_IDEMPOTENCY_KEY'), (
        f'Idempotency header was not recognized by the live API: '
        f'{probe_code} {probe_body}. Check proxies and server version.')
    print('Header probe: server recognized Idempotency-Key (422 for deliberately invalid key).')
    name = 'Idempotency Demo ' + uuid.uuid4().hex[:10]
    snack_id = None
    try:
        status, snack = api('POST', '/snacks', admin_token, {
            'name': name, 'category': 'savoury', 'quantity': 3, 'low_stock_threshold': 5})
        assert status == 201, f'Create failed: {status}, {snack}'
        snack_id = snack['id']
        url = f'/snacks/{snack_id}/consume'
        key = 'smoke-retry-' + uuid.uuid4().hex
        barrier = Barrier(10)

        def worker(_):
            barrier.wait(timeout=20)
            return api('POST', url, member_token, {'amount': 1}, key)

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(worker, range(10)))
        statuses = [code for code, _ in results]
        assert statuses == [200] * 10, f'Expected ten 200 replays, got: {results}'
        assert all(payload == results[0][1] for _, payload in results), 'Replayed bodies were not identical'
        status, current = api('GET', f'/snacks/{snack_id}', member_token)
        assert status == 200 and current['quantity'] == 2, f'Stock was decremented more than once: {current}'
        print('10 simultaneous HTTP requests, SAME key: 10 x 200; quantity 3 -> 2 (once only).')

        status, bad = api('POST', url, member_token, {'amount': 2}, key)
        assert status == 409 and bad['error']['code'] == 'IDEMPOTENCY_KEY_REUSED', (status, bad)
        print('Same key with DIFFERENT amount: 409 IDEMPOTENCY_KEY_REUSED.')

        status, retry = api('POST', url, member_token, {'amount': 1}, key)
        assert status == 200 and retry == results[0][1]
        print('Late retry with original key: original 200 body replayed.')

        status, history = api('GET', '/activity?page=1&page_size=50', admin_token)
        assert status == 200
        entries = [entry for entry in history['items'] if entry['snack_name'] == name]
        assert len(entries) == 1 and entries[0]['action'] == 'consumed', entries
        print('Exactly one activity record: VERIFIED.')
        print('PASS: same-key concurrent retries cannot double-consume.')
    finally:
        if snack_id is not None:
            status, body = api('DELETE', f'/snacks/{snack_id}', admin_token)
            if status != 204:
                print(f'Warning: cleanup failed: {status} {body}', file=sys.stderr)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, TimeoutError, ValueError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)
