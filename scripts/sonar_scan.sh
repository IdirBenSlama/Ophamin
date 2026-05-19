#!/usr/bin/env bash
# scripts/sonar_scan.sh — run a SonarQube scan against a Kimera-SWM
# checkout (or any Python codebase) using Ophamin's bundled
# sonar-project.properties.
#
# Pre-reqs:
#   - SonarQube stack running (`bash scripts/sonar_up.sh`)
#   - SONAR_TOKEN env var set (generate at http://localhost:9000/account/security)
#
# Usage:
#   SONAR_TOKEN=<token> bash scripts/sonar_scan.sh /path/to/Kimera_SWM
#   SONAR_TOKEN=<token> bash scripts/sonar_scan.sh /path/to/Kimera_SWM --with-coverage
#
# Optional flags:
#   --with-coverage    Run pytest --cov first; pass coverage.xml to Sonar
#   --with-ruff        Run ruff first; pass JSON report to Sonar
#   --with-bandit      Run bandit first; pass JSON report to Sonar
#
# The scanner uses Docker (sonarsource/sonar-scanner-cli) so no host
# install required — works on any machine with Docker.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || (cd "$(dirname "$0")/.." && pwd))"

if [[ $# -lt 1 ]]; then
    echo "ERROR: target path required" >&2
    echo "Usage: $0 /path/to/Kimera_SWM [--with-coverage] [--with-ruff] [--with-bandit]" >&2
    exit 1
fi

TARGET="$1"
shift
if [[ ! -d "$TARGET" ]]; then
    echo "ERROR: target path is not a directory: $TARGET" >&2
    exit 1
fi
TARGET="$(cd "$TARGET" && pwd)"

WITH_COVERAGE=0
WITH_RUFF=0
WITH_BANDIT=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --with-coverage) WITH_COVERAGE=1 ;;
        --with-ruff)     WITH_RUFF=1 ;;
        --with-bandit)   WITH_BANDIT=1 ;;
        *) echo "WARN: unknown flag: $1" >&2 ;;
    esac
    shift
done

if [[ -z "${SONAR_TOKEN:-}" ]]; then
    echo "ERROR: SONAR_TOKEN env var is required." >&2
    echo "  Generate at http://localhost:9000/account/security" >&2
    echo "  Then: export SONAR_TOKEN=<your-token>" >&2
    exit 1
fi

PROPS="$REPO_ROOT/sonar/sonar-project.kimera-swm.properties"
if [[ ! -f "$PROPS" ]]; then
    echo "ERROR: $PROPS not found." >&2
    exit 1
fi

# Pre-flight: is SonarQube reachable?
if ! curl --silent --fail --max-time 5 http://localhost:9000/api/system/status > /dev/null 2>&1; then
    echo "ERROR: SonarQube at http://localhost:9000 not reachable." >&2
    echo "  Bring it up first: bash scripts/sonar_up.sh" >&2
    exit 1
fi

echo "▶ Target:  $TARGET"
echo "▶ Config:  $PROPS"
echo

# Optional: coverage
if [[ $WITH_COVERAGE -eq 1 ]]; then
    echo "▶ Running pytest --cov for coverage..."
    (cd "$TARGET" && pytest --cov=kimera_swm --cov-report=xml:coverage.xml -q 2>&1 || true) \
        | tail -5
    if [[ -f "$TARGET/coverage.xml" ]]; then
        echo "✓ coverage.xml generated."
    else
        echo "WARN: coverage.xml not produced; SonarQube coverage will be 0%."
    fi
    echo
fi

# Optional: ruff report
if [[ $WITH_RUFF -eq 1 ]]; then
    echo "▶ Running ruff check..."
    (cd "$TARGET" && ruff check --output-format=sarif -o ruff-report.json kimera_swm/ 2>&1 || true) \
        | tail -3
    echo
fi

# Optional: bandit report
if [[ $WITH_BANDIT -eq 1 ]]; then
    echo "▶ Running bandit..."
    (cd "$TARGET" && bandit -r kimera_swm/ -f json -o bandit-report.json -q 2>&1 || true) \
        | tail -3
    echo
fi

# Copy the bundled properties file into the target so the scanner picks it up.
cp "$PROPS" "$TARGET/sonar-project.properties"

# The scanner uses --network=host so it can reach localhost:9000 on the
# host. (On Docker Desktop, this is the standard pattern.)
echo "▶ Running sonar-scanner..."
docker run --rm \
    --network=host \
    -e SONAR_TOKEN="$SONAR_TOKEN" \
    -v "$TARGET:/usr/src" \
    sonarsource/sonar-scanner-cli:latest

# Clean up the copied properties file (avoid polluting the Kimera checkout).
rm -f "$TARGET/sonar-project.properties"

echo
echo "✓ Scan complete."
echo "  Open: http://localhost:9000/dashboard?id=kimera-swm"
