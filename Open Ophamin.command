#!/bin/bash
# Double-click this file to open the Ophamin console in your browser.
#
# It starts Ophamin's local server and opens the "Start here" page automatically.
# A small Terminal window stays open while it runs — just close it (or press
# Ctrl+C) when you're done. Nothing leaves your computer; the server is local only.
cd "$(dirname "$0")" || exit 1
if [ -x ".venv/bin/ophamin" ]; then
  exec .venv/bin/ophamin http serve --open
else
  echo "Ophamin's environment (.venv) was not found next to this file."
  echo "Expected: $(pwd)/.venv/bin/ophamin"
  echo "Press any key to close."
  read -r -n 1
  exit 1
fi
