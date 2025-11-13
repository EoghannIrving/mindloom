#!/usr/bin/env bash
set -euo pipefail
venv_ruff="$(pwd)/.venv/bin/ruff"
if [[ -x "$venv_ruff" ]]; then
  "$venv_ruff" check . --select E9,F63,F7,F82 --show-source
else
  echo "ruff not available; skipping CI-style lint (offline environment)" >&2
fi
