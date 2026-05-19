#!/usr/bin/env bash
#
# Apply the pre-baked Kimera-SWM quality gate to the running SonarQube
# instance via its REST API. Idempotent — re-running creates the gate
# if missing OR updates its conditions to match the JSON spec.
#
# Usage:
#   bash scripts/sonar_apply_quality_gate.sh sonar/kimera-swm-quality-gate.json
#
# Environment:
#   SONAR_BASE_URL  default: http://localhost:9000
#   SONAR_TOKEN     a SonarQube user token (required; passed as HTTP
#                   Basic user, empty password).
#   SONAR_PROJECT   default: kimera-swm — the project the gate binds to.
#
# Exits non-zero on any REST error so the script is safe to wire into
# CI / GitOps post-deploy hooks.

set -euo pipefail

GATE_JSON="${1:?usage: sonar_apply_quality_gate.sh <gate.json>}"
BASE_URL="${SONAR_BASE_URL:-http://localhost:9000}"
TOKEN="${SONAR_TOKEN:?SONAR_TOKEN is required (a SonarQube user token)}"
PROJECT="${SONAR_PROJECT:-kimera-swm}"

if [[ ! -f "$GATE_JSON" ]]; then
    echo "ERROR: gate file not found: $GATE_JSON" >&2
    exit 1
fi

# Need jq for parsing the spec; loud-fail if absent.
if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: jq is required (brew install jq / apt install jq)" >&2
    exit 1
fi

GATE_NAME=$(jq -r '.name' "$GATE_JSON")
if [[ -z "$GATE_NAME" || "$GATE_NAME" == "null" ]]; then
    echo "ERROR: gate JSON missing top-level 'name' field" >&2
    exit 1
fi

echo "Applying Quality Gate '$GATE_NAME' to project '$PROJECT' on $BASE_URL"

# --- ensure the gate exists, idempotently ---
existing=$(curl -fsS -u "$TOKEN:" "$BASE_URL/api/qualitygates/list" \
    | jq -r --arg n "$GATE_NAME" '.qualitygates[] | select(.name == $n) | .name' \
    || true)

if [[ -z "$existing" ]]; then
    echo "Creating gate '$GATE_NAME'..."
    curl -fsS -X POST -u "$TOKEN:" \
        --data-urlencode "name=$GATE_NAME" \
        "$BASE_URL/api/qualitygates/create" >/dev/null
fi

# --- wipe + re-add conditions to match the spec ---
# Portable to macOS bash 3.2 — no `mapfile` (bash 4+ only).
echo "Re-applying conditions..."
existing_ids=$(curl -fsS -u "$TOKEN:" \
    "$BASE_URL/api/qualitygates/show?name=$(jq -rn --arg n "$GATE_NAME" '$n|@uri')" \
    | jq -r '.conditions[]?.id // empty')

while IFS= read -r cid; do
    [[ -z "$cid" ]] && continue
    curl -fsS -X POST -u "$TOKEN:" \
        --data-urlencode "id=$cid" \
        "$BASE_URL/api/qualitygates/delete_condition" >/dev/null
done <<<"$existing_ids"

# Add each condition from the spec.
jq -c '.conditions[]' "$GATE_JSON" | while IFS= read -r cond; do
    metric=$(jq -r '.metric' <<<"$cond")
    op=$(jq -r '.op' <<<"$cond")
    err=$(jq -r '.error' <<<"$cond")
    echo "  + condition: $metric $op $err"
    curl -fsS -X POST -u "$TOKEN:" \
        --data-urlencode "gateName=$GATE_NAME" \
        --data-urlencode "metric=$metric" \
        --data-urlencode "op=$op" \
        --data-urlencode "error=$err" \
        "$BASE_URL/api/qualitygates/create_condition" >/dev/null
done

# --- bind the gate to the project ---
echo "Binding gate '$GATE_NAME' to project '$PROJECT'..."
curl -fsS -X POST -u "$TOKEN:" \
    --data-urlencode "gateName=$GATE_NAME" \
    --data-urlencode "projectKey=$PROJECT" \
    "$BASE_URL/api/qualitygates/select" >/dev/null

echo "Done. Re-run the scan (bash scripts/sonar_scan.sh <repo>) to evaluate against the new gate."
