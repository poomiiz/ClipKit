# Start the Video -> CapCut tool hidden on 8770 and open the page.
# Already running = only open the page. Logs: app\video_editor.log / .out.log
$app = $PSScriptRoot
$url = "http://127.0.0.1:8770/video-editor.html"
$up = $false
try { $up = (Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 2).StatusCode -eq 200 } catch {}
if (-not $up) {
    $py = (Get-Command python -ErrorAction Stop).Source
    Start-Process -FilePath $py -ArgumentList "app.py" -WorkingDirectory $app -WindowStyle Hidden `
        -RedirectStandardError "$app\video_editor.log" -RedirectStandardOutput "$app\video_editor.out.log"
    for ($i = 0; $i -lt 20 -and -not $up; $i++) {
        Start-Sleep -Milliseconds 500
        try { $up = (Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 2).StatusCode -eq 200 } catch {}
    }
}
Start-Process $url
