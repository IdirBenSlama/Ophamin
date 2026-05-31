#!/usr/bin/env bash
# scripts/integrations_down.sh — stop the local integration services started by
# integrations_up.sh (MLflow :5000, mkdocs :8000). Does NOT touch your existing
# Grafana / Prometheus / SonarQube stack — those are yours.
set -uo pipefail
for spec in "mlflow server.*5000|MLflow :5000" "mkdocs serve.*8000|mkdocs :8000"; do
  pat="${spec%%|*}"; name="${spec##*|}"
  pids="$(pgrep -f "$pat" 2>/dev/null || true)"
  if [ -n "$pids" ]; then echo "→ stopping $name ($pids)"; kill $pids 2>/dev/null || true; else echo "✓ $name not running"; fi
done
