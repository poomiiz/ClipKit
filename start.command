#!/usr/bin/env bash
set -euo pipefail
repo_root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
python_bin="$repo_root/.venv/bin/python"
if [[ ! -x "$python_bin" ]]; then
  printf '%s\n' "Run bash scripts/setup.sh first to set up this Mac." >&2
  exit 1
fi
exec "$python_bin" "$repo_root/scripts/start.py" "$@"
