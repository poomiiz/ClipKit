# Start the Video -> CapCut tool hidden on 8770 and open the page.
# Already running = only open the page. Shared controller verifies process ownership.
$app = $PSScriptRoot
# the team edition runs on its own port, so it never opens the other ClipKit on the same machine
$port = if ((git -C "$app\.." remote get-url origin 2>$null) -like "*ClipKit-Team*") { 8771 } else { 8770 }
$url = "http://127.0.0.1:$port/video-editor.html"
& (Join-Path $app 'control.ps1') -Action start -Port $port | Out-Null
# open as its own app window (no address bar or tabs) so it feels like a program, not a web page;
# Chrome first, else Edge (every Windows 10/11 has it), else a normal browser tab
$win = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
         "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
         "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
         "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
         "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
$opened = $false
if ($win) { try { Start-Process $win -ArgumentList "--app=$url", "--window-size=1320,860" -ErrorAction Stop; $opened = $true } catch {} }
if (-not $opened) { Start-Process $url }
