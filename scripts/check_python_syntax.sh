#!/usr/bin/env bash
set -euo pipefail
venv_python="$(pwd)/.venv/bin/python"
mapfile -t pyfiles < <(git ls-files '*.py')
if (( ${#pyfiles[@]} )); then
  "$venv_python" -m py_compile "${pyfiles[@]}"
else
  echo "No Python files to check."
fi
