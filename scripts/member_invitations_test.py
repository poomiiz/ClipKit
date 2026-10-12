"""First-login invitation routing; provider tokens stay server-side."""
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
import team_hub as hub

def main():
    app = FastAPI()
    app.include_router(hub.router)
    org = '00000000-0000-0000-0000-000000000010'
    invite = {'organization_id': org, 'organization_name': 'Invited team', 'role': 'editor'}
    data = {'access_token': 'private-access', 'refresh_token': 'private-refresh', 'expires_in': 3600,
            'user': {'id': 'user', 'email': 'future@example.test'}}
    for count in (0, 1, 2):
        hub._sessions.clear()
        calls = []
        admitted = False
        def provider(path, method='GET', body=None, token=''):
            nonlocal admitted
            calls.append((path, body, token))
            if path.startswith('/auth/'): return data
            assert token == 'private-access'
            if path.endswith('/clipkit_pending_invitations'): return [invite] * count
            if path.endswith('/clipkit_accept_invitation'):
                assert body == {'org': org}
                admitted = True
                return org
            if path.startswith('/rest/v1/clipkit_organizations'): return [{'id': org}] if admitted else []
            raise AssertionError(path)
        with TestClient(app) as client, patch.object(hub, '_config', return_value=('https://hub.example.test', 'public')), patch.object(hub, '_provider', side_effect=provider):
            assert client.get('/invitations').status_code == 404
            assert client.get('/api/team/invitations').status_code == 401
            client.post('/api/team/login', json={'email': 'future@example.test', 'password': 'password'})
            result = client.get('/api/team/organizations')
            assert result.status_code == 200
            assert admitted == (count == 1)
            assert 'private-access' not in result.text
            if count == 2:
                assert len(client.get('/api/team/invitations').json()) == 2
                assert client.post('/api/team/invitations/' + org + '/accept').json() == {'id': org}
    print('PASS first-login single invitation, explicit multiple choice and authenticated token boundary')

if __name__ == '__main__':
    main()
