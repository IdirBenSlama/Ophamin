#!/usr/bin/env bash
# scripts/sonar_down.sh — bring down the SonarQube + PostgreSQL stack.
#
# Default (no flag): stop containers but PRESERVE volumes (re-up later
# resumes where you left off, including all scan history).
#
# --wipe: ALSO delete the named volumes (destroys ALL SonarQube history,
#         scan results, user accounts, project configs).
#
# Usage:
#   bash scripts/sonar_down.sh           # stop, preserve state
#   bash scripts/sonar_down.sh --wipe    # stop AND wipe state

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || (cd "$(dirname "$0")/.." && pwd))"
cd "$REPO_ROOT"

COMPOSE_FILE="sonar/docker-compose.yml"
if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "ERROR: $COMPOSE_FILE not found. Run from the Ophamin repo root." >&2
    exit 1
fi

WIPE=0
if [[ "${1:-}" == "--wipe" ]]; then
    WIPE=1
fi

if [[ $WIPE -eq 1 ]]; then
    # Confirm before destroying state — `--wipe` removes ALL scan
    # history, user accounts, generated tokens, custom quality gates.
    # Force --yes via env var for non-interactive callers (CI cleanup).
    if [[ "${OPHAMIN_SONAR_WIPE_CONFIRMED:-}" != "yes" ]]; then
        echo "WARNING: --wipe will DESTROY all SonarQube data:" >&2
        echo "  - All scan history" >&2
        echo "  - All user accounts + tokens" >&2
        echo "  - All projects + quality gates" >&2
        echo
        read -r -p "Type 'wipe' to confirm: " confirm
        if [[ "$confirm" != "wipe" ]]; then
            echo "Aborted." >&2
            exit 1
        fi
    fi
    echo "▶ Stopping containers + removing named volumes..."
    docker compose -f "$COMPOSE_FILE" down -v
    echo "✓ SonarQube stack stopped + state wiped."
else
    echo "▶ Stopping containers (state preserved)..."
    docker compose -f "$COMPOSE_FILE" down
    echo "✓ SonarQube stack stopped."
    echo "  Volumes preserved; resume with: bash scripts/sonar_up.sh"
fi
