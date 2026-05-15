"""Mine Kimera's field-schema against the real substrate (Layer A live run).

Streams a small balanced text-stimulus set through every Kimera target and
records every field that appears in ``CycleResult.raw``. The output is a
SchemaDocument JSON + a human-readable Markdown reference, both pinned to
the Kimera + Ophamin git commits and the stimulus-set content hash.

Re-run this script after each meaningful Kimera change; ``ophamin
discover-diff`` then surfaces structural drift (added / removed / type-
changed fields) between consecutive runs.

    PYTHONPATH=src .venv/bin/python -u examples/run_kimera_discovery.py
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ophamin.cli import DEFAULT_DISCOVERY_STIMULI, DEFAULT_DISCOVERY_TARGETS
from ophamin.seeing.discovery import SchemaMiner, write_schema_markdown
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
OUT_DIR = Path("discovery")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — LAYER A: KIMERA FIELD-SCHEMA DISCOVERY")
    targets = list(DEFAULT_DISCOVERY_TARGETS)
    stimuli = list(DEFAULT_DISCOVERY_STIMULI)
    print(f"targets  : {', '.join(targets)}")
    print(f"stimuli  : {len(stimuli)} (balanced text)")

    # one adapter to bootstrap; SchemaMiner constructs per-target adapters
    substrate = KimeraAdapter(
        REPO, target=targets[0], mode="batch", batch_timeout=900.0
    )
    miner = SchemaMiner(substrate)

    try:
        doc = miner.mine(targets=targets, stimuli=stimuli)
    except Exception:  # noqa: BLE001 — surface the real failure
        banner("DISCOVERY RAISED")
        traceback.print_exc()
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    short = (doc.kimera_git_commit or "unknown")[:12]
    json_path = OUT_DIR / f"kimera_fields_{short}.json"
    md_path = OUT_DIR / f"kimera_fields_{short}.md"
    doc.to_json(json_path)
    write_schema_markdown(doc, md_path)

    banner("DISCOVERY RESULT")
    print(f"kimera commit       : {doc.kimera_git_commit}")
    print(f"ophamin commit      : {doc.ophamin_git_commit}")
    print(f"stimulus hash       : {doc.stimulus_set_hash[:16]}…")
    print(f"captured at         : {doc.captured_at}")
    print(f"targets probed      : {len(doc.targets)}")
    for t in doc.targets:
        print(f"  {t.name:<10}  fields: {len(t.fields):>3}  "
              f"cycles: {t.n_cycles}  adapter_errors: {t.n_adapter_errors}")
    print(f"written             : {json_path}")
    print(f"                      {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
