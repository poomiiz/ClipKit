"""Mandatory login protects local pages and APIs; provider calls are stubbed."""
import sys
import time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from fastapi.testclient import TestClient
from app import app
import team_hub as hub


def sign_in(client, data):
    """A provider session as the Google callback leaves it; password sign-in no longer exists."""
    hub._sessions['test-session'] = {**data, 'expires_at': time.time() + 3600, 'ends_at': time.time() + 86400}
    client.cookies.set(hub.COOKIE, 'test-session')

def main():
    hub._sessions.clear()
    data = {'access_token': 'private-access', 'refresh_token': 'private-refresh', 'expires_in': 3600,
            'user': {'id': 'u1', 'email': 'editor@example.test'}}
    with TestClient(app, base_url='http://127.0.0.1:8770') as client, patch.object(hub, '_config', return_value=('https://hub.example.test', 'public')), patch.object(hub, '_provider', return_value=data):
        for page in ('/', '/video-editor.html', '/styles.html', '/settings.html', '/team.html', '/review.html', '/REVIEW.html', '/motion/private.html'):
            result = client.get(page, follow_redirects=False)
            assert result.status_code == 303 and result.headers['location'] == '/login.html', page
        for method, path in [('GET', '/api/video/drafts'), ('POST', '/api/kit/locate'), ('GET', '/api/team/setup'), ('POST', '/api/team/setup'), ('GET', '/docs'), ('GET', '/openapi.json')]:
            assert client.request(method, path).status_code == 401, path
        for asset in ('/login.html', '/login.js', '/login.css', '/logo.svg', '/ui.js', '/i18n/en.json'):
            response = client.get(asset)
            assert response.status_code == 200, asset
            csp = response.headers['content-security-policy']
            assert csp == csp.strip(), 'CSP header has whitespace rejected by the real HTTP server'
        assert client.get('/api/team/session').json()['signed_in'] is False
        assert client.get('/api/window/health').status_code == 200
        assert client.post('/api/team/google', json={}).status_code == 200
        for gone in ('/api/team/login', '/api/team/signup'):   # password accounts were removed; Google only
            assert client.post(gone, json={'email': 'editor@example.test', 'password': 'password'}).status_code == 401, gone
        sign_in(client, data)
        # GET clients sometimes send Content-Type without a body; this is not invalid JSON.
        assert client.get('/video-editor.html', headers={'Content-Type': 'application/json'}).status_code == 200
        assert client.get('/api/team/setup').status_code == 200
        sid = client.cookies.get(hub.COOKIE)
        hub._sessions[sid]['ends_at'] = 0
        assert client.get('/api/video/drafts').status_code == 401
        assert client.get('/video-editor.html', follow_redirects=False).headers['location'] == '/login.html'
    print('PASS mandatory page/API login, public entry assets, Google start, expiry and empty GET body')

if __name__ == '__main__':
    main()
