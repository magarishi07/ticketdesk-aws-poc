"""API tests against a deployed TicketDesk (laptop or AWS).

  export APP_URL=https://<distribution>.cloudfront.net
  export ADMIN_PASSWORD='<from Secrets Manager>'
  pytest -v tests/api
"""
import os

import pytest
import requests

BASE = os.environ.get('APP_URL', 'http://localhost:8000').rstrip('/')
PASSWORD = os.environ.get('ADMIN_PASSWORD', '')
PNG = b'\x89PNG\r\n\x1a\n' + b'0' * 100

pytestmark = pytest.mark.skipif(not PASSWORD, reason='ADMIN_PASSWORD not set')


@pytest.fixture(scope='module')
def s():
    session = requests.Session()
    r = session.post(f'{BASE}/login', data={'username': 'admin', 'password': PASSWORD},
                     allow_redirects=False, timeout=10)
    assert r.status_code == 303
    return session


def test_health():
    assert requests.get(f'{BASE}/health', timeout=10).json()['status'] == 'ok'


def test_wrong_password_rejected():
    r = requests.post(f'{BASE}/login', data={'username': 'admin', 'password': 'wrong'}, timeout=10)
    assert r.status_code == 401


def test_pages_need_login():
    r = requests.get(f'{BASE}/tickets', allow_redirects=False, timeout=10)
    assert r.status_code == 303 and r.headers['location'] == '/login'


def test_dashboard(s):
    assert 'Dashboard' in s.get(f'{BASE}/', timeout=10).text


def test_ticket_lifecycle_with_attachment(s):
    r = s.post(f'{BASE}/tickets',
               data={'title': 'VPN not connecting', 'description': 'Error 809 since morning', 'priority': 'High'},
               files={'file': ('screenshot.png', PNG, 'image/png')}, allow_redirects=False, timeout=20)
    assert r.status_code == 303
    path = r.headers['location']
    page = s.get(f'{BASE}{path}', timeout=10).text
    assert 'VPN not connecting' in page and 'screenshot.png' in page
    for expected in ['In Progress', 'Resolved', 'Closed']:
        s.post(f'{BASE}{path}/status', timeout=10)
        assert f'<b>Status:</b> {expected}' in s.get(f'{BASE}{path}', timeout=10).text
    r = s.post(f'{BASE}{path}/status', allow_redirects=False, timeout=10)
    assert r.status_code == 400  # a closed ticket cannot move further


def test_ticket_list_filter(s):
    assert 'Tickets (Closed)' in s.get(f'{BASE}/tickets', params={'status': 'Closed'}, timeout=10).text
