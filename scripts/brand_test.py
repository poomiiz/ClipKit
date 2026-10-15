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
import re, sync_team
private_names = re.compile(r"ExamplePerson|poomiiz", re.I)
assert not sync_team.names_in(b'https://github.com/poomiiz/EditorKrab', private_names)
assert not sync_team.names_in(b'https://github.com/poomiiz/ClipKit', private_names)
assert sync_team.names_in(b'private client ExamplePerson', private_names)
print('PASS EditorKrab assets, visible brand and legacy identifier compatibility')

# Windows PowerShell 5 reads non-BOM UTF-8 as an ANSI code page.
import os,subprocess
if os.name=='nt':
 shell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
 for name in ('app/start.ps1','scripts/setup.ps1'):
  script=root/name
  assert script.read_bytes().startswith(b'\xef\xbb\xbf'),name
  escaped=str(script).replace("'","''")
  command="$errors=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('"+escaped+"',[ref]$null,[ref]$errors);if($errors.Count){$errors | ForEach-Object {$_.Message};exit 1}"
  subprocess.run([str(shell),'-NoProfile','-Command',command],check=True,capture_output=True)
 print('PASS Windows PowerShell desktop launcher and setup parse Thai strings')

assert (root/"app/static/editorkrab-crab.ico").read_bytes()==(root/"app/static/editorkrab.ico").read_bytes()
import make_promo
voice=(root/'docs/brand/promo-voiceover.md').read_text(encoding='utf-8')
for start,end,line in make_promo.LINES:
 assert 0 <= start < end <= make_promo.DUR and line in voice
for phrase in ('ready-to-post','one click','hours of','edit less','post more'):
 assert phrase not in (root/'scripts/make_promo.py').read_text(encoding='utf-8').lower(),phrase
assert 'Workflow illustration' in (root/'scripts/make_promo.py').read_text(encoding='utf-8')
assert 'Mac setup: experimental' in (root/'scripts/make_promo.py').read_text(encoding='utf-8')
assert make_promo.F(40).getlength('relaxed vlog, funny parts, under 1 min|') <= 740
for script in ("app/start.ps1","scripts/setup.ps1"):
 assert "editorkrab-crab.ico" in (root/script).read_text(encoding="utf-8-sig")
