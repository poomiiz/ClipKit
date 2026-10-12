"""Local Google PKCE boundary checks; no live Google account is used."""
import sys,base64,hashlib
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from fastapi.testclient import TestClient
from app import app
import team_hub as hub

def main():
 hub._oauth.clear();hub._sessions.clear()
 session={'access_token':'private-access','refresh_token':'private-refresh','expires_in':3600,'user':{'id':'u1','email':'owner@example.test','user_metadata':{'full_name':'Google Owner'}}}
 with TestClient(app,base_url='http://127.0.0.1:8770') as client,patch.object(hub,'_config',return_value=('https://hub.example.test','public')),patch.object(hub,'_provider',return_value=session) as provider:
  assert client.post('/api/team/google',headers={'Origin':'https://evil.example'}).status_code==403
  start=client.post('/api/team/google',json={});assert start.status_code==200
  assert 'httponly' in start.headers['set-cookie'].lower() and 'samesite=lax' in start.headers['set-cookie'].lower()
  query=parse_qs(urlsplit(start.json()['url']).query);callback=query['redirect_to'][0];state=parse_qs(urlsplit(callback).query)['state'][0]
  verifier=hub._oauth[state]['verifier']
  assert query['provider']==['google'] and query['code_challenge_method']==['s256']
  assert query['code_challenge']==[base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')]
  assert verifier not in start.text
  assert client.get(callback.replace(state,'wrong')+'&code=forged',follow_redirects=False).status_code==400
  with TestClient(app,base_url='http://127.0.0.1:8770') as other:
   assert other.get(callback+'&code=stolen',follow_redirects=False).status_code==400
  provider.assert_not_called()
  headers={'sec-fetch-site':'cross-site','sec-fetch-mode':'navigate','sec-fetch-dest':'document'}
  assert client.get('/api/team/organizations',headers=headers).status_code==403
  result=client.get(callback+'&code=provider-code',headers=headers,follow_redirects=False)
  assert result.status_code==303 and result.headers['location']=='/team.html'
  provider.assert_called_once_with('/auth/v1/token?grant_type=pkce','POST',{'auth_code':'provider-code','code_verifier':verifier})
  assert 'private-access' not in result.text and 'private-refresh' not in result.text
  assert 'samesite=strict' in result.headers['set-cookie'].lower()
  assert client.get('/api/team/session').json()['user']['display_name']=='Google Owner'
  assert client.get(callback+'&code=provider-code',follow_redirects=False).status_code==400
  for case in ('expired','cancel','reject'):
   start=client.post('/api/team/google',json={});callback=parse_qs(urlsplit(start.json()['url']).query)['redirect_to'][0];state=parse_qs(urlsplit(callback).query)['state'][0]
   if case=='expired':hub._oauth[state]['expires_at']=0
   if case=='reject':provider.return_value={}
   result=client.get(callback+('&error=access_denied' if case=='cancel' else '&code=code'),follow_redirects=False)
   assert result.status_code==(400 if case=='expired' else 303)
   if case!='expired':assert result.headers['location']=='/login.html?login_error=1'
   assert state not in hub._oauth
 print('PASS Google PKCE, browser binding, expiry, replay, cancellation and token boundary')
if __name__=='__main__':main()
