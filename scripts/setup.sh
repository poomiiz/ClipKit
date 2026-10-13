#!/usr/bin/env bash
# macOS setup: workspace paths in config.json, packages in this clone's venv.
set -euo pipefail
if [[ "$(uname -s)" != "Darwin" ]]; then
  printf '%s\n' "This installer is for macOS. On Windows, use setup.cmd." >&2
  exit 1
fi
repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
workspace_path="$HOME/EditorKrab Workspace"
if [[ $# -gt 0 && "$1" != --* ]]; then workspace_path="$1"; shift; fi
ensure_tool() {
  local tool="$1" formula="$2"
  if ! command -v "$tool" >/dev/null 2>&1; then
    if ! command -v brew >/dev/null 2>&1; then
      printf 'Missing %s. Install it yourself, or install Homebrew from https://brew.sh and run setup again.\n' "$tool" >&2
      exit 1
    fi
    brew install "$formula"
    export PATH="$(brew --prefix "$formula")/bin:$PATH"
  fi
  command -v "$tool" >/dev/null 2>&1 || { printf 'Cannot find %s after installation.\n' "$tool" >&2; exit 1; }
}
ensure_tool python3.12 python@3.12
ensure_tool ffmpeg ffmpeg-full
ffmpeg_filters="$(ffmpeg -hide_banner -filters 2>/dev/null)"
ffmpeg_encoders="$(ffmpeg -hide_banner -encoders 2>/dev/null)"
if [[ "$ffmpeg_filters" != *" subtitles "* || "$ffmpeg_encoders" != *" libx264 "* ]]; then
  command -v brew >/dev/null 2>&1 || { printf '%s\n' "ffmpeg needs subtitle and libx264 support. Install a compatible build, or install Homebrew and rerun setup." >&2; exit 1; }
  brew install ffmpeg-full
  export PATH="$(brew --prefix ffmpeg-full)/bin:$PATH"
fi
ensure_tool node node@22
command -v npx >/dev/null 2>&1 || { printf '%s\n' "Node is installed but npx is missing." >&2; exit 1; }
if [[ ! -d "$repo_root/.venv" ]]; then python3.12 -m venv "$repo_root/.venv"; fi
python_bin="$repo_root/.venv/bin/python"
"$python_bin" -c 'import sys; assert sys.version_info[:2] == (3, 12), "This workspace needs a Python 3.12 virtual environment"'
"$python_bin" -m pip install -r "$repo_root/requirements.txt"
"$python_bin" "$repo_root/scripts/setup_macos.py" --workspace "$workspace_path" \
  --tool-bin "$(dirname -- "$(command -v ffmpeg)")" \
  --tool-bin "$(dirname -- "$(command -v node)")" "$@"
printf '%s\n' "Ready. Double-click start.command to open EditorKrab."
