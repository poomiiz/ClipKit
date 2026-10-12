"""Self-check distributable EditorKrab assets and compatibility identifiers."""
from pathlib import Path
import json,xml.etree.ElementTree as ET
from PIL import Image
root=Path(__file__).resolve().parents[1]
for name in ('icon','logo','logo-dark','github-banner'):
 ET.parse(root/'docs/brand'/f'{name}.svg')
for path,size in [('app/static/logo-256.png',(256,256)),('docs/brand/icon-512.png',(512,512)),('docs/brand/icon-1024.png',(1024,1024)),('docs/brand/github-banner.png',(1280,640))]:
 with Image.open(root/path) as im:assert im.size==size;im.verify()
with Image.open(root/'app/static/editorkrab.ico') as im:
 assert {(16,16),(32,32),(48,48),(256,256)} <= im.ico.sizes()
assert (root/'app/static/clipkit.ico').read_bytes()==(root/'app/static/editorkrab.ico').read_bytes()
for path in (root/'app/static').glob('*.html'):
 assert 'ClipKit' not in path.read_text(encoding='utf-8'),path
assert 'EditorKrab' in (root/'app/static/shell.js').read_text(encoding='utf-8')
assert '"clip-kit"' in (root/'.claude-plugin/plugin.json').read_text(encoding='utf-8')
assert '"clipkit"' in (root/'app/static/team.html').read_text(encoding='utf-8')
import sync_team
assert not sync_team.names_in(b'https://github.com/poomiiz/EditorKrab')
assert not sync_team.names_in(b'https://github.com/poomiiz/ClipKit')
assert sync_team.names_in(b'private client poomi')
print('PASS EditorKrab assets, visible brand and legacy identifier compatibility')
