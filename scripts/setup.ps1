# ClipKit one-time machine setup (Windows). Safe to re-run.
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Workspace D:\EditorKrab
# -Workspace (optional) also makes config.json and every folder under it, then runs the full check.
param([string]$Workspace = "")
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Run([string[]]$cmd) {
    & python @cmd
    if ($LASTEXITCODE -ne 0) { throw "failed: python $($cmd -join ' ')" }
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

if (-not (Test-Path "$root\config.json")) {
    Copy-Item "$root\config.example.json" "$root\config.json"
    if (-not $Workspace) { Write-Host "Created config.json - open it and set your folders, then run the check below." }
}
if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { Run "$root\scripts\use_cpu.py" }

# Desktop icon for the Video -> CapCut app
$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) "EditorKrab.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = "powershell.exe"
$s.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$root\app\start.ps1`""
$s.WorkingDirectory = $root
$s.IconLocation = "$root\app\static\editorkrab-crab.ico"
$s.Description = "EditorKrab — ตัดคลิป จัดงาน จบในทีม"
$s.Save()
Write-Host "Desktop icon created: $lnk"

if ($Workspace) { Run "$root\scripts\setup_workspace.py", $Workspace }
Run "$root\scripts\fetch_model.py"
if ($Workspace) { Run "$root\scripts\doctor.py", "--asr" } else { Run "$root\scripts\doctor.py" }
