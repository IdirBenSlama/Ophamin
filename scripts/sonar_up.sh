#!/usr/bin/env bash
# scripts/sonar_up.sh — bring up the SonarQube + PostgreSQL stack.
#
# Idempotent: re-running brings up any service that's down, leaves
# already-running services alone. Blocks until SonarQube reports
# healthy (or the 4-min timeout expires).
#
# Usage:
#   bash scripts/sonar_up.sh                  # start + wait for healthy
#   bash scripts/sonar_up.sh --detach         # start; don't wait
#
# After healthy:
#   http://localhost:9000          # default admin / admin
#
# Then: change admin password (forced on first login) and generate a
# user token at /account/security; export SONAR_TOKEN for the scan step.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || (cd "$(dirname "$0")/.." && pwd))"
cd "$REPO_ROOT"

COMPOSE_FILE="sonar/docker-compose.yml"
if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "ERROR: $COMPOSE_FILE not found. Run from the Ophamin repo root." >&2
    exit 1
fi

DETACH_ONLY=0
if [[ "${1:-}" == "--detach" ]]; then
    DETACH_ONLY=1
fi

# Pre-flight: docker daemon reachable?
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: docker daemon not reachable. Start Docker Desktop / dockerd." >&2
    exit 1
fi

echo "▶ Bringing up SonarQube + PostgreSQL..."
docker compose -f "$COMPOSE_FILE" up -d

if [[ $DETACH_ONLY -eq 1 ]]; then
    echo "▶ Started (detached). Check health with: docker compose -f $COMPOSE_FILE ps"
    exit 0
fi

echo "▶ Waiting for SonarQube to report healthy (timeout: 4 min)..."
deadline=$(( $(date +%s) + 240 ))
while [[ $(date +%s) -lt $deadline ]]; do
    status=$(docker compose -f "$COMPOSE_FILE" ps --format json sonarqube 2>/dev/null \
        | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('Health','unknown'))" 2>/dev/null \
        || echo "starting")
    case "$status" in
        healthy)
            echo "✓ SonarQube is healthy."
            echo
            echo "  Web UI:    http://localhost:9000"
            echo "  Login:     admin / admin (change on first login)"
            echo "  Token:     generate at http://localhost:9000/account/security"
            echo "             then export SONAR_TOKEN=<your-token>"
            echo
            echo "  Scan a Kimera-SWM checkout next:"
            echo "    SONAR_TOKEN=<token> bash scripts/sonar_scan.sh /path/to/Kimera_SWM"
            exit 0
            ;;
        unhealthy)
            echo "ERROR: SonarQube container reported UNHEALTHY." >&2
            docker compose -f "$COMPOSE_FILE" logs --tail=50 sonarqube
            exit 1
            ;;
    esac
    sleep 5
    printf "."
done

echo
echo "ERROR: SonarQube did not become healthy within 4 minutes." >&2
echo "Last logs:" >&2
docker compose -f "$COMPOSE_FILE" logs --tail=50 sonarqube >&2
exit 1
