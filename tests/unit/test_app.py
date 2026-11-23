"""Unit tests: run the app against a temporary SQLite file (no AWS, no PostgreSQL).

Run from the app folder:  cd app && python -m pytest ../tests/unit -v
"""
import os

os.environ['DATABASE_URL'] = 'sqlite:///./test.db'
os.environ['SESSION_SECRET'] = 'test-only-secret'
os.environ['ADMIN_PASSWORD'] = 'test-only-pass'
os.environ.pop('S3_BUCKET', None)
os.environ.pop('APP_SECRET_NAME', None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def logged_in(client):
    r = client.post('/login', data={'username': 'admin', 'password': 'test-only-pass'}, follow_redirects=False)
    assert r.status_code == 303
    return client


def test_health(client):
    assert client.get('/health').json()['status'] == 'ok'


def test_login_required(client):
    r = client.get('/tickets', follow_redirects=False)
    assert r.status_code == 303


def test_wrong_password(client):
    r = client.post('/login', data={'username': 'admin', 'password': 'nope'})
    assert r.status_code == 401


def test_ticket_lifecycle(logged_in):
    r = logged_in.post('/tickets', data={'title': 'Printer jam', 'description': 'Floor 3', 'priority': 'Low'},
                       files={'file': ('notes.txt', b'paper stuck', 'text/plain')}, follow_redirects=False)
    assert r.status_code == 303
    path = r.headers['location']
    assert 'notes.txt' in logged_in.get(path).text
    for status in ['In Progress', 'Resolved', 'Closed']:
        logged_in.post(f'{path}/status')
        assert f'<b>Status:</b> {status}' in logged_in.get(path).text
    assert logged_in.post(f'{path}/status', follow_redirects=False).status_code == 400
