"""End-to-end HTTP smoke test against a RUNNING Snack Overflow API.

Run `python scripts/smoke_http.py` after `docker compose up --build`.
Creates and removes its own uniquely named test snack. Uses only Python stdlib.
Never point this script at a real, shared production service.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import os
import sys
import uuid

BASE = os.getenv('SNACK_API_URL', 'http://localhost:8000').rstrip('/')


def api(method, path, token=None, payload=None):
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = Request(f'{BASE}{path}', data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except HTTPError as exc:
        raw = exc.read()
        return exc.code, json.loads(raw) if raw else None


def race(action, count=10):
    barrier = Barrier(count)
    def worker(_):
        barrier.wait(timeout=20)
        return action()[0]
    with ThreadPoolExecutor(max_workers=count) as pool:
        return Counter(pool.map(worker, range(count)))


def main():
    status, health = api('GET', '/health')
    assert status == 200, f'API not healthy: {status}, {health}'
    admin_code, admin = api('POST', '/auth/login', payload={
        'email': 'admin@snackoverflow.dev', 'password': 'Admin123!'})
    member_code, member = api('POST', '/auth/login', payload={
        'email': 'member@snackoverflow.dev', 'password': 'Member123!'})
    assert admin_code == member_code == 200, 'Demo logins failed; run the seed script first.'
    admin_token = admin['token']
    member_token = member['token']
    snack_id = None
    name = 'HTTP Race Test ' + uuid.uuid4().hex[:10]
    try:
        status, created = api('POST', '/snacks', admin_token, {
            'name': name, 'category': 'savoury', 'quantity': 3, 'low_stock_threshold': 5})
        assert status == 201, f'Cannot create test snack: {status}, {created}'
        snack_id = created['id']
        path = f'/snacks/{snack_id}'
        print(f'Created disposable snack #{snack_id} with 3 packets.')

        consumption = race(lambda: api('POST', path + '/consume', member_token, {'amount': 1}))
        print('Ten simultaneous HTTP consume requests:', dict(consumption))
        assert consumption == Counter({200: 3, 409: 7}), 'Expected exactly 3 successes and 7 conflicts.'
        status, snack = api('GET', path, member_token)
        assert status == 200 and snack['quantity'] == 0, f'Unexpected stock: {snack}'

        vote_codes = race(lambda: api('POST', path + '/vote', member_token))
        print('Ten simultaneous HTTP votes by one user:', dict(vote_codes))
        assert vote_codes == Counter({201: 1, 409: 9}), 'Duplicate votes were accepted.'
        status, snack = api('GET', path, member_token)
        assert status == 200 and snack['votes'] == 1, f'Unexpected votes: {snack}'

        status, denied = api('POST', path + '/restock', member_token, {'amount': 5})
        assert status == 403, f'Member should be forbidden to restock, got {status}: {denied}'
        status, snack = api('POST', path + '/restock', admin_token, {'amount': 5})
        assert status == 200 and snack['quantity'] == 5, 'Admin restock was not recorded.'

        events = []
        page = 1
        while True:
            status, result = api('GET', f'/activity?page={page}&page_size=50', admin_token)
            assert status == 200
            events.extend(item for item in result['items'] if item['snack_name'] == name)
            if page >= result['pages']:
                break
            page += 1
        assert len(events) == 4, f'Expected 3 consumes + 1 restock, got {len(events)} events.'
        assert sum(e['action'] == 'consumed' for e in events) == 3
        assert sum(e['action'] == 'restocked' for e in events) == 1
        print('Verified quantity=5 after admin restock and 4 consistent audit entries.')
        print('Verified member REST authorization: 403 for restock.')
        print('PASS: Live HTTP API, atomic stock, unique votes, permissions, and audit trail.')
    finally:
        if snack_id is not None:
            status, response = api('DELETE', f'/snacks/{snack_id}', admin_token)
            if status != 204:
                print(f'Warning: could not clean up test snack #{snack_id}: {status}, {response}', file=sys.stderr)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, URLError, TimeoutError, ValueError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)
