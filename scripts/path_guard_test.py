"""Local file endpoints stay inside their folders: traversal, a folder outside the roots and a linked project."""
import base64
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app import app
import kit_settings
import team_hub as hub


def rejected(path: str) -> bool:
    try:
        kit_settings._project(path)
    except HTTPException as exc:
        return exc.status_code == 400
    return False


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        drafts, outside, music = tmp / 'drafts', tmp / 'outside', tmp / 'music'
        for d in (drafts / 'mine', outside / 'theirs', drafts / 'mine' / 'clipkit_hf', music):
            d.mkdir(parents=True)
        for d in (drafts / 'mine', outside / 'theirs'):
            (d / 'draft_content.json').write_text('{}', encoding='utf-8')
        (drafts / 'mine' / 'clipkit_hf' / 'index.html').write_text('<p>ok</p>', encoding='utf-8')
        (tmp / 'secret.mp3').write_bytes(b'ID3')
        (music / 'song.mp3').write_bytes(b'ID3')
        linked = drafts / 'linked'
        try:
            os.symlink(outside / 'theirs', linked, target_is_directory=True)
        except OSError:
            linked = None   # Windows without symlink rights: the check below is skipped there
        with patch.object(kit_settings, '_read_config', return_value={'capcut_drafts': str(drafts)}):
            assert kit_settings._project(str(drafts / 'mine'))[0] == 'capcut'
            assert rejected(str(outside / 'theirs')), 'project outside the drafts folder'
            assert rejected(str(drafts / 'mine' / '..' / '..' / 'outside' / 'theirs')), 'dot-dot out of drafts'
            if linked:
                assert rejected(str(linked)), 'linked folder points outside the drafts folder'

        hub._sessions['test-session'] = {'access_token': 'a', 'refresh_token': 'r', 'user': {'id': 'u1'},
                                         'expires_at': time.time() + 3600, 'ends_at': time.time() + 86400}
        key = base64.urlsafe_b64encode(str(drafts / 'mine').encode()).decode().rstrip('=')
        with TestClient(app, base_url='http://127.0.0.1:8770') as client, \
                patch.dict(os.environ, {'MUSIC_DIRS': str(music)}):
            client.cookies.set(hub.COOKIE, 'test-session')
            assert client.get(f'/api/video/hfp/{key}/index.html').status_code == 200
            for escape in ('..%2Fdraft_content.json', '%2E%2E/%2E%2E/%2E%2E/secret.mp3', '..%5Cdraft_content.json'):
                assert client.get(f'/api/video/hfp/{key}/{escape}').status_code == 404, escape
            assert client.get('/api/video/file', params={'path': str(music / 'song.mp3')}).status_code == 200
            assert client.get('/api/video/file', params={'path': str(tmp / 'secret.mp3')}).status_code == 403
            assert client.get('/api/video/file', params={'path': str(music / '..' / 'secret.mp3')}).status_code == 403
            assert client.get('/api/kit/cover-frame/..%2F..%2Fsecret.mp3').status_code == 404
            assert client.get('/api/video/file', params={'path': str(music / 'song.mp3')},
                              headers={'Origin': 'http://evil.example'}).status_code == 403
        hub._sessions.clear()
    print('PASS path guards: hfp traversal, music folder, cover frame, project roots, cross-origin')


if __name__ == '__main__':
    main()
