"""Public sign-up: normalization, security, uniqueness, and member-only access."""
from sqlalchemy import select
from app.models import User
from app.security import verify_password


def test_register_creates_hashed_member_and_logs_in(setup):
    client, factory, _ = setup
    response = client.post('/auth/register', json={
        'name': '  New Colleague  ',
        'email': 'New.Colleague@Example.COM',
        'password': 'Welcome123!',
    })
    assert response.status_code == 201, response.text
    result = response.json()
    assert result['user']['name'] == 'New Colleague'
    assert result['user']['email'] == 'new.colleague@example.com'
    assert result['user']['role'] == 'member'
    assert result['token']
    assert 'password' not in result and 'password_hash' not in result['user']
    with factory() as db:
        user = db.scalar(select(User).where(User.email == 'new.colleague@example.com'))
        assert user is not None
        assert user.password_hash != 'Welcome123!'
        assert verify_password('Welcome123!', user.password_hash)
    token_headers = {'Authorization': f"Bearer {result['token']}"}
    assert client.get('/auth/me', headers=token_headers).json()['role'] == 'member'
    assert client.get('/snacks', headers=token_headers).status_code == 200


def test_duplicate_email_case_insensitive_and_clean_error(setup):
    client, factory, _ = setup
    payload = {'name': 'Jane Doe', 'email': 'jane@example.com', 'password': 'Password123!'}
    assert client.post('/auth/register', json=payload).status_code == 201
    dup = client.post('/auth/register', json={**payload, 'email': 'JANE@EXAMPLE.COM'})
    assert dup.status_code == 409
    assert dup.json() == {'error': {'code': 'EMAIL_ALREADY_REGISTERED', 'message': 'This email address is already registered. Please sign in.'}}
    with factory() as db:
        assert len(db.scalars(select(User).where(User.email == 'jane@example.com')).all()) == 1


def test_existing_seeded_email_cannot_register_again(setup):
    client, _, _ = setup
    response = client.post('/auth/register', json={
        'name': 'Fake Admin', 'email': 'ADMIN@TEST.DEV', 'password': 'Password123!'
    })
    assert response.status_code == 409


def test_cannot_choose_admin_role_or_insert_extra_fields(setup):
    client, factory, _ = setup
    result = client.post('/auth/register', json={
        'name': 'Intruder', 'email': 'intruder@example.com', 'password': 'Password123!', 'role': 'admin'
    })
    assert result.status_code == 422
    assert result.json()['error']['code'] == 'VALIDATION_ERROR'
    with factory() as db:
        assert db.scalar(select(User).where(User.email == 'intruder@example.com')) is None


def test_register_validates_name_email_and_password(setup):
    client, _, _ = setup
    base = {'name': 'New User', 'email': 'new.user@example.com', 'password': 'Password123!'}
    invalid = [
        {**base, 'name': '   '},
        {**base, 'email': 'not-an-email'},
        {**base, 'password': 'abc'},
        {**base, 'password': 'allletters'},
        {**base, 'password': '123456789'},
        {**base, 'name': 'A\nB'},
    ]
    for body in invalid:
        response = client.post('/auth/register', json=body)
        assert response.status_code == 422, (body, response.text)
        assert response.json()['error']['code'] == 'VALIDATION_ERROR'


def test_new_member_cannot_access_admin_endpoints(setup):
    client, _, ids = setup
    result = client.post('/auth/register', json={
        'name': 'Regular Member', 'email': 'regular@example.com', 'password': 'Password123!'
    })
    assert result.status_code == 201
    auth = {'Authorization': f"Bearer {result.json()['token']}"}
    assert client.post(f"/snacks/{ids['snack']}/restock", headers=auth, json={'amount': 5}).status_code == 403
    assert client.post('/snacks', headers=auth, json={
        'name': 'Should Not Exist', 'category': 'sweet', 'quantity': 1,
    }).status_code == 403
