# ClipKit one-time machine setup (Windows). Safe to re-run.
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Ensure($cmd, $wingetId, $label) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) { return }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw "$label is missing and winget is not available - install $label by hand" }
    Write-Host "Installing $label..."
    winget install --id $wingetId -e --silent --accept-source-agreements --accept-package-agreements
    Refresh-Path
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$label installed but '$cmd' is not on PATH yet - open a new terminal and run setup again" }
}

Ensure python "Python.Python.3.12" "Python 3.12"
Ensure ffmpeg "Gyan.FFmpeg" "ffmpeg"
Ensure npx "OpenJS.NodeJS.LTS" "Node.js (MP4 export)"

Write-Host "Installing Python packages..."
python -m pip install -r "$root\requirements.txt"
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    # ctranslate2 (faster-whisper) needs CUDA 12 cuBLAS/cuDNN on Windows
    python -m pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
}

$chrome = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe", "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) {
    Write-Host "Installing Google Chrome (needed for Envato search/download)..."
    winget install --id Google.Chrome -e --silent --accept-source-agreements --accept-package-agreements
}

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
$s.IconLocation = "$root\app\static\clipkit.ico"
$s.Save()
Write-Host "Desktop icon created: $lnk"

python "$root\scripts\fetch_model.py"
python "$root\scripts\doctor.py"
Write-Host "Envato: run 'python scripts\envato.py login' once and sign in (each download uses a licence on that account)."
