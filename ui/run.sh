#!/usr/bin/env bash
# Run Vidatron UI from the updatedui folder.
# Uses venv if present; otherwise system python (ensure kivy is installed).

set -e
cd "$(dirname "$0")"

# Avoid Kivy writing to ~/.kivy when we can't (e.g. in sandbox or read-only home)
export KIVY_NO_FILELOG="${KIVY_NO_FILELOG:-1}"

if [[ -d venv ]]; then
  exec ./venv/bin/python main.py "$@"
else
  exec python3 main.py "$@"
fi
