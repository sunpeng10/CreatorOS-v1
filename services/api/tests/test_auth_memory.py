"""Login memory uses revocable sessions, never saved account passwords."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie

from fastapi.testclient import TestClient
from sqlalchemy import select


@contextmanager
def database():
    from app.main import app
    from app.db import get_db
    generator = app.dependency_overrides[get_db]()
    try:
        yield next(generator)
    finally:
        generator.close()


ACCOUNT = {'email': 'remember@example.test', 'password': 'Test-Password-482!', 'name': '测试账号'}


def test_remembered_login_survives_client_reopen_and_logout_revokes_it(client):
    from app.auth import COOKIE
    assert client.post('/api/auth/register', json=ACCOUNT).status_code == 200
    response = client.post('/api/auth/login', json={**ACCOUNT, 'remember_me': True})
    cookie = SimpleCookie(response.headers['set-cookie'])[COOKIE]
    assert int(cookie['max-age']) == 30 * 86400
    assert cookie['expires'] and cookie['httponly'] and cookie['samesite'] == 'lax'
    token = client.cookies.get(COOKIE)
    with TestClient(client.app) as reopened:
        reopened.cookies.set(COOKIE, token)
        assert reopened.get('/api/auth/me').status_code == 200
        assert client.post('/api/auth/logout').status_code == 200
        assert reopened.get('/api/auth/me').status_code == 401


def test_unchecked_login_does_not_set_a_persistent_cookie(client):
    from app.auth import COOKIE
    client.post('/api/auth/register', json=ACCOUNT)
    response = client.post('/api/auth/login', json={**ACCOUNT, 'remember_me': False})
    cookie = SimpleCookie(response.headers['set-cookie'])[COOKIE]
    assert not cookie['max-age'] and not cookie['expires']
    assert cookie['httponly']
    assert client.get('/api/auth/me').status_code == 200


def test_server_expiry_cannot_be_bypassed_by_remembered_cookie(client):
    from app.models import Session
    client.post('/api/auth/register', json={**ACCOUNT, 'remember_me': True})
    with database() as db:
        record = db.scalar(select(Session))
        assert record.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc) + timedelta(days=29)
        record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert client.get('/api/auth/me').status_code == 401


def test_new_login_replaces_old_remembered_session(client):
    from app.auth import COOKIE
    client.post('/api/auth/register', json={**ACCOUNT, 'remember_me': True})
    prior = client.cookies.get(COOKIE)
    assert client.post('/api/auth/login', json={**ACCOUNT, 'remember_me': True}).status_code == 200
    assert client.cookies.get(COOKIE) != prior
    with TestClient(client.app) as other:
        other.cookies.set(COOKIE, prior)
        assert other.get('/api/auth/me').status_code == 401
    assert client.get('/api/auth/me').status_code == 200
