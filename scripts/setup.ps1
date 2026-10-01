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

if (-not (Test-Path "$root\config.json")) {
    Copy-Item "$root\config.example.json" "$root\config.json"
    Write-Host "Created config.json - open it and set your folders, then run the check below."
}

python "$root\scripts\doctor.py"
