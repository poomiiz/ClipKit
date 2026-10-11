# Start the Video -> CapCut tool hidden on 8770 and open the page.
# Already running = only open the page. Logs: app\video_editor.log / .out.log
$app = $PSScriptRoot
# the team edition runs on its own port, so it never opens the other ClipKit on the same machine
$port = if ((git -C "$app\.." remote get-url origin 2>$null) -like "*ClipKit-Team*") { 8771 } else { 8770 }
$env:VIDEO_EDITOR_PORT = "$port"
# desktop shortcuts made before the ClipKit logo still show a stock Windows icon: point them at clipkit.ico
$root = Split-Path $app
$ico = "$app\static\clipkit.ico"
$sh = New-Object -ComObject WScript.Shell
foreach ($f in Get-ChildItem ([Environment]::GetFolderPath('Desktop')) -Filter *.lnk) {
    $l = $sh.CreateShortcut($f.FullName)
    if ("$($l.TargetPath) $($l.Arguments) $($l.WorkingDirectory)" -like "*$root*" -and $l.IconLocation -notlike "$ico*") {
        $l.IconLocation = $ico; $l.Save()
    }
}
$url = "http://127.0.0.1:$port/video-editor.html"
# already running = only open the page; the shared controller starts it and waits until /api/window/health is ready
# a refusal (e.g. a copy started by hand before this controller) is written to control.log and the window still opens
try { & (Join-Path $app 'control.ps1') -Action start -Port $port | Out-Null }
catch { Add-Content "$app\control.log" "$(Get-Date -Format s) start: $_" }
# open as its own app window (no address bar or tabs) so it feels like a program, not a web page;
# Chrome first, else Edge (every Windows 10/11 has it), else a normal browser tab
$win = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
         "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
         "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
         "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
         "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
$opened = $false
# its own browser profile: a ClipKit window opened inside the person's running Chrome can stay grey when that
# Chrome is stuck, while the same page in a normal tab works (10 Oct 2026)
$winProfile = "$env:LOCALAPPDATA\ClipKit\window"
if ($win) { try { Start-Process $win -ArgumentList "--app=$url", "--window-size=1320,860", "--user-data-dir=`"$winProfile`"", "--no-first-run" -ErrorAction Stop; $opened = $true } catch {} }
if (-not $opened) { Start-Process $url }
