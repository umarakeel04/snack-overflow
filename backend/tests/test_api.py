"""Business requirements tested through the real HTTP API."""
from sqlalchemy import select
from app.models import Activity, Snack, Vote


def test_requires_login(setup):
    client, _, _ = setup
    for path in ("/snacks", "/snacks/summary", "/activity", "/auth/me"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_login_logout_and_expiration(setup):
    client, _, _ = setup
    bad = client.post('/auth/login', json={'email': 'member@test.dev', 'password': 'wrong'})
    assert bad.status_code == 401
    assert bad.json()['error']['code'] == 'INVALID_CREDENTIALS'
    response = client.post('/auth/login', json={'email': 'member@test.dev', 'password': 'Password123!'})
    assert response.status_code == 200
    token = response.json()['token']
    assert response.json()['user']['role'] == 'member'
    headers = {'Authorization': f'Bearer {token}'}
    assert client.get('/auth/me', headers=headers).status_code == 200
    assert client.post('/auth/logout', headers=headers).status_code == 204
    assert client.get('/auth/me', headers=headers).status_code == 401


def test_admin_only_for_write_operations(setup, auth):
    client, _, ids = setup
    member = auth['member']
    attempts = [
        client.post('/snacks', headers=member, json={'name': 'New', 'category': 'sweet', 'quantity': 1}),
        client.patch(f"/snacks/{ids['snack']}", headers=member, json={'name': 'Changed'}),
        client.delete(f"/snacks/{ids['snack']}", headers=member),
        client.post(f"/snacks/{ids['snack']}/restock", headers=member, json={'amount': 5}),
        client.get('/activity', headers=member),
    ]
    assert [response.status_code for response in attempts] == [403] * len(attempts)
    assert all(response.json()['error']['code'] == 'FORBIDDEN' for response in attempts)
    assert client.get('/snacks', headers=member).status_code == 200


def test_atomic_consume_and_activity(setup, auth):
    client, factory, ids = setup
    route = f"/snacks/{ids['snack']}/consume"
    assert client.post(route, headers=auth['member'], json={'amount': 2}).status_code == 200
    result = client.post(route, headers=auth['member'], json={'amount': 2})
    assert result.status_code == 409
    assert result.json()['error']['code'] == 'INSUFFICIENT_STOCK'
    with factory() as db:
        snack = db.get(Snack, ids['snack'])
        assert snack.quantity == 1
        history = db.scalars(select(Activity).where(Activity.snack_id == snack.id)).all()
        assert [(a.action, a.amount, a.user_id) for a in history] == [('consumed', 2, ids['member'])]


def test_restock_and_activity_audited(setup, auth):
    client, factory, ids = setup
    response = client.post(f"/snacks/{ids['snack']}/restock", headers=auth['admin'], json={'amount': 8})
    assert response.status_code == 200
    assert response.json()['quantity'] == 11
    history = client.get('/activity', headers=auth['admin']).json()
    assert history['total'] == 1
    assert history['items'][0]['action'] == 'restocked'
    assert history['items'][0]['amount'] == 8
    with factory() as db:
        assert db.get(Snack, ids['snack']).quantity == 11


def test_vote_database_uniqueness_and_unvote(setup, auth):
    client, factory, ids = setup
    route = f"/snacks/{ids['snack']}/vote"
    response = client.post(route, headers=auth['member'])
    assert response.status_code == 201
    assert response.json()['votes'] == 1 and response.json()['has_voted']
    response = client.post(route, headers=auth['member'])
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'ALREADY_VOTED'
    with factory() as db:
        assert len(db.scalars(select(Vote)).all()) == 1
    assert client.delete(route, headers=auth['member']).status_code == 200
    assert client.delete(route, headers=auth['member']).status_code == 409
    assert client.post(route, headers=auth['member']).status_code == 201


def test_snack_creation_edit_delete_and_validation(setup, auth):
    client, _, ids = setup
    headers = auth['admin']
    result = client.post('/snacks', headers=headers, json={'name': '  Mocha Latte  ', 'category': 'drink', 'quantity': 2})
    assert result.status_code == 201
    snack = result.json()
    assert snack['name'] == 'Mocha Latte'
    assert snack['status'] == 'running_low'
    assert client.post('/snacks', headers=headers, json={'name': 'Mocha Latte', 'category': 'drink'}).status_code == 409
    assert client.post('/snacks', headers=headers, json={'name': 'MOCHA LATTE', 'category': 'drink'}).status_code == 409
    result = client.patch(f"/snacks/{snack['id']}", headers=headers, json={'low_stock_threshold': 1})
    assert result.status_code == 200 and result.json()['status'] == 'stocked'
    assert client.patch(f"/snacks/{snack['id']}", headers=headers, json={'quantity': 999}).status_code == 422 # quantity changes must go through audited endpoints
    assert client.get(f"/snacks/{snack['id']}", headers=headers).json()['quantity'] == 2
    assert client.delete(f"/snacks/{snack['id']}", headers=headers).status_code == 204
    assert client.get(f"/snacks/{snack['id']}", headers=headers).status_code == 404
    assert client.get('/snacks/does-not-exist', headers=headers).status_code == 422


def test_invalid_amounts_and_uniform_errors(setup, auth):
    client, _, ids = setup
    route = f"/snacks/{ids['snack']}/consume"
    for bad in [0, -1, 1000001, 1.5, 'not-a-number']:
        response = client.post(route, headers=auth['member'], json={'amount': bad})
        assert response.status_code == 422, response.text
        assert response.json()['error']['code'] == 'VALIDATION_ERROR'
    assert client.post('/snacks', headers=auth['admin'], json={'name': ' ', 'category': 'sweet'}).status_code == 422
    assert client.post('/snacks', headers=auth['admin'], json={'name': 'test', 'category': 'unknown'}).status_code == 422


def test_status_filter_search_sort_and_pagination(setup, auth):
    client, _, ids = setup
    headers = auth['admin']
    for name, qty in [('Cookies', 10), ('Cola', 0), ('Chips', 2)]:
        assert client.post('/snacks', headers=headers, json={'name': name, 'category': 'sweet', 'quantity': qty}).status_code == 201
    resp = client.get('/snacks?status=gone', headers=headers)
    assert resp.json()['total'] == 1 and resp.json()['items'][0]['name'] == 'Cola'
    resp = client.get('/snacks?q=co&category=sweet', headers=headers)
    assert resp.json()['total'] == 2
    resp = client.get('/snacks?sort=quantity&order=desc&page_size=2&page=1', headers=headers)
    assert resp.json()['total'] == 4 and resp.json()['pages'] == 2
    assert [s['quantity'] for s in resp.json()['items']] == [10, 3]
    assert client.get('/snacks?page=0', headers=headers).status_code == 422
    summary = client.get('/snacks/summary', headers=headers).json()
    assert (summary['stocked'], summary['running_low'], summary['gone'], summary['total']) == (1, 2, 1, 4)
    assert summary['snack_of_the_week'] is None


def test_weekly_winner_and_delete_keeps_activity(setup, auth):
    client, _, ids = setup
    assert client.post(f"/snacks/{ids['snack']}/vote", headers=auth['member']).status_code == 201
    summary = client.get('/snacks/summary', headers=auth['member']).json()
    assert summary['snack_of_the_week']['name'] == 'Masala Peanuts'
    assert summary['snack_of_the_week']['votes_this_week'] == 1
    assert client.post(f"/snacks/{ids['snack']}/consume", headers=auth['member'], json={'amount': 1}).status_code == 200
    assert client.delete(f"/snacks/{ids['snack']}", headers=auth['admin']).status_code == 204
    history = client.get('/activity', headers=auth['admin']).json()
    assert history['total'] == 1 and history['items'][0]['snack_name'] == 'Masala Peanuts'
