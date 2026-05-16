#!/usr/bin/env bash
# scripts/generate_sbom.sh — emit a CycloneDX SBOM of the current venv (Phase S5).
#
# Two outputs:
#
#   sbom/ophamin.cdx.json      — machine-readable CycloneDX 1.5 (uploadable to
#                                Dependency-Track, GitHub dependency graph, etc.)
#   sbom/ophamin.cdx.txt       — human-readable per-component summary
#
# Optionally also runs osv-scanner against the SBOM if osv-scanner is on PATH
# (or installed in .venv/bin/) — that surfaces upstream CVE advisories from
# the OSV database without leaving local-only files.
#
# Usage:
#   bash scripts/generate_sbom.sh                # generate only
#   bash scripts/generate_sbom.sh --scan         # generate + osv-scanner
#   bash scripts/generate_sbom.sh --scan --strict  # exit non-zero on any vuln

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

SBOM_DIR="${REPO_ROOT}/sbom"
mkdir -p "$SBOM_DIR"

if [[ -x ".venv/bin/python" ]]; then
    PY=".venv/bin/python"
else
    PY="python"
fi

JSON_OUT="${SBOM_DIR}/ophamin.cdx.json"
TXT_OUT="${SBOM_DIR}/ophamin.cdx.txt"

echo "▶ Generating CycloneDX SBOM via ophamin's own interop wheel..."

"$PY" <<'PY_EOF'
"""Use ophamin's own CycloneDX exporter to emit the SBOM.

This is intentional: the exporter is part of the interop wheel and ships
to consumers. Using it here is the canonical reference call, exercising
the same code path operators will use against signed proof records.
"""
import json
from pathlib import Path
from ophamin.interop.cyclonedx import build_cyclonedx_sbom_from_env

import ophamin
sbom = build_cyclonedx_sbom_from_env(
    application_name="ophamin",
    application_version=ophamin.__version__,
)

json_path = Path("sbom/ophamin.cdx.json")
txt_path = Path("sbom/ophamin.cdx.txt")
json_path.write_text(json.dumps(sbom, indent=2, default=str), encoding="utf-8")

# Companion text summary — one line per component, easy to grep / eyeball.
lines = []
lines.append(f"# ophamin SBOM — CycloneDX {sbom.get('specVersion', '?')}")
lines.append(f"# bomFormat={sbom.get('bomFormat', '?')}  serialNumber={sbom.get('serialNumber', '?')}")
metadata = sbom.get("metadata", {})
lines.append(f"# generated_at={metadata.get('timestamp', '?')}")
tool_entries = metadata.get("tools") or {}
if isinstance(tool_entries, dict):
    for c in tool_entries.get("components", []) or []:
        lines.append(f"# generator={c.get('group', '')}/{c.get('name', '?')} {c.get('version', '?')}")
lines.append("")
for comp in sbom.get("components", []) or []:
    name = comp.get("name", "?")
    version = comp.get("version", "?")
    purl = comp.get("purl", "")
    lines.append(f"{name:<40} {version:<20} {purl}")
lines.append("")
lines.append(f"# total components: {len(sbom.get('components', []) or [])}")
txt_path.write_text("\n".join(lines), encoding="utf-8")
print(f"  wrote {json_path}")
print(f"  wrote {txt_path}")
print(f"  components: {len(sbom.get('components', []) or [])}")
PY_EOF

# osv-scanner integration (optional)
SCAN=0
STRICT=0
for arg in "$@"; do
    case "$arg" in
        --scan) SCAN=1 ;;
        --strict) STRICT=1 ;;
    esac
done

if [[ "$SCAN" -eq 1 ]]; then
    OSV_BIN=""
    if [[ -x ".venv/bin/osv-scanner" ]]; then
        OSV_BIN=".venv/bin/osv-scanner"
    elif command -v osv-scanner >/dev/null 2>&1; then
        OSV_BIN="osv-scanner"
    fi

    if [[ -z "$OSV_BIN" ]]; then
        echo "▶ osv-scanner not installed; install via:"
        echo "    go install github.com/google/osv-scanner/cmd/osv-scanner@v2.0.3"
        echo "    or:  brew install osv-scanner"
        if [[ "$STRICT" -eq 1 ]]; then
            exit 2
        fi
    else
        echo "▶ Running osv-scanner against $JSON_OUT ..."
        if "$OSV_BIN" --sbom "$JSON_OUT"; then
            echo "✔ osv-scanner: no advisories"
        else
            STATUS=$?
            echo "⚠ osv-scanner reported advisories (exit $STATUS)"
            if [[ "$STRICT" -eq 1 ]]; then
                exit "$STATUS"
            fi
        fi
    fi
fi

echo "✔ SBOM artefacts ready in $SBOM_DIR/"
