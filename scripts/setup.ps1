# ClipKit one-time machine setup (Windows). Safe to re-run.
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3.12 is not installed: winget install Python.Python.3.12" }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "Installing ffmpeg..."
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    Write-Host "Open a new terminal afterwards so ffmpeg is on PATH."
}

Write-Host "Installing Python packages..."
python -m pip install -r "$root\requirements.txt"
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    # ctranslate2 (faster-whisper) needs CUDA 12 cuBLAS/cuDNN on Windows
    python -m pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
}

$chrome = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe", "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { throw "Google Chrome is required for Envato search/download: winget install Google.Chrome" }

if (-not (Test-Path "$root\config.json")) {
    Copy-Item "$root\config.example.json" "$root\config.json"
    Write-Host "Created config.json - open it and set your folders, then run the check below."
}

# Desktop icon for the Video -> CapCut app
$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) "ClipKit - Video to CapCut.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = "powershell.exe"
$s.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$root\app\start.ps1`""
$s.WorkingDirectory = $root
$s.IconLocation = "C:\Windows\System32\imageres.dll,184"
$s.Save()
Write-Host "Desktop icon created: $lnk"

python "$root\scripts\doctor.py"
Write-Host "Envato: run 'python scripts\envato.py login' once and sign in (each download uses a licence on that account)."
