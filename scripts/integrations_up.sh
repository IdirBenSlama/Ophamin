#!/usr/bin/env bash
# scripts/integrations_up.sh — bring up Ophamin's local integration services and
# launch the HTTP server WIRED to them, so the 3 locally-runnable integrations
# (MLflow, Documentation, Grafana) show "connected" persistently.
#
# Why a script and not a .env: `ophamin http serve` does NOT auto-load a .env for
# its own OPHAMIN_*_URL vars, so the wiring has to be exported into the server's
# environment at launch. This script does that + starts the support services.
#
# Idempotent (sonar_up.sh convention): starts a service only if its port is free;
# leaves running ones alone.
#
# Usage:
#   bash scripts/integrations_up.sh            # start services + serve (foreground)
#   OPHAMIN_GRAFANA_URL=… bash scripts/integrations_up.sh   # override any URL
#
# Wires 3 of 6 integrations. The other 3 aren't locally runnable — point them at
# your own services by exporting their vars before running (see the block below):
#   OPHAMIN_DVC_URL   — DVC Studio (cloud-hosted)
#   OPHAMIN_PROV_URL  — a PROV-O provenance viewer
#   OPHAMIN_SARIF_URL — GitHub Code Scanning, or a SARIF viewer
set -euo pipefail
cd "$(dirname "$0")/.."
VENV="${VENV:-.venv}"

_port_free() { ! lsof -ti "tcp:$1" >/dev/null 2>&1; }

# MLflow (run tracking / comparison) — :5000
if _port_free 5000; then
  echo "→ starting MLflow on :5000"
  nohup "$VENV/bin/mlflow" server --host 127.0.0.1 --port 5000 \
    --backend-store-uri "file:$PWD/mlruns" >/tmp/ophamin-mlflow.log 2>&1 &
else
  echo "✓ MLflow already on :5000"
fi

# Documentation (mkdocs) — :8000
if _port_free 8000; then
  echo "→ starting mkdocs docs on :8000"
  nohup "$VENV/bin/mkdocs" serve --dev-addr 127.0.0.1:8000 >/tmp/ophamin-mkdocs.log 2>&1 &
else
  echo "✓ mkdocs already on :8000"
fi

# Wire the env the server reads. Grafana defaults to your existing instance
# (kimera-grafana / any Grafana on :3000); override OPHAMIN_GRAFANA_URL as needed.
export OPHAMIN_MLFLOW_URL="${OPHAMIN_MLFLOW_URL:-http://localhost:5000}"
export OPHAMIN_DOCS_URL="${OPHAMIN_DOCS_URL:-http://localhost:8000/Ophamin/}"
export OPHAMIN_GRAFANA_URL="${OPHAMIN_GRAFANA_URL:-http://localhost:3000}"

# Code scanning (SARIF) → this repo's GitHub Code Scanning (derived from the git
# remote). Refresh the findings with:
#   .venv/bin/ophamin audit src/ophamin --pillars ruff,bandit --out-dir audits/
#   .venv/bin/ophamin export audits/<latest>.json --format sarif --output o.sarif
#   gh api repos/<owner>/<repo>/code-scanning/sarifs -X POST --input <body>   # gzip+base64 + repo-relative URIs
_ghslug="$(git config --get remote.origin.url 2>/dev/null | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')"
[ -n "$_ghslug" ] && export OPHAMIN_SARIF_URL="${OPHAMIN_SARIF_URL:-https://github.com/$_ghslug/security/code-scanning}"

sleep 2
echo "→ serving Ophamin on :8137 (MLflow + Docs + Grafana wired)"
exec "$VENV/bin/python" -m ophamin http serve --host 127.0.0.1 --port 8137 "$@"
