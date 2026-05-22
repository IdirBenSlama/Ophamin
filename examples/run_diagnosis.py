"""Run the diagnosis agent on a signed proof using a local model.

The live-model bridge in action: the agentic system performs the analysis,
routed to the dedicated SCIENTIFIC tier. The model is local (Ollama /
LMStudio / MLX-LM) — never in the measurement path, only analysing an
already-signed proof. The structured diagnosis is written next to the proof
as ``diagnosis.json`` (an analysis artifact alongside the signed record).

Point the SCIENTIFIC tier at a local model via env, e.g. LMStudio:

    OPHAMIN_LLM_BASE_URL=http://localhost:1234/v1 \
    OPHAMIN_LLM_MODEL_SCIENTIFIC="qwen/qwen3.5-35b-a3b" \
    PYTHONPATH=src .venv/bin/python -u examples/run_diagnosis.py <proof.json> [--write]

Or Ollama (default base): set OPHAMIN_LLM_MODEL_SCIENTIFIC to an installed tag.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from ophamin.agentic.agents.result_diagnosis import diagnose


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    write = "--write" in sys.argv
    if not args:
        print(__doc__)
        return 2
    proof_path = Path(args[0])
    if not proof_path.is_file():
        print(f"proof not found: {proof_path}")
        return 2

    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    banner(f"OPHAMIN — DIAGNOSE {proof.get('proof_id', '')[:16]}")
    v = proof.get("verdict", {})
    print(f"verdict : {v.get('outcome')} · observed {v.get('observed_value')}")
    print("model   : SCIENTIFIC tier (dedicated) — see /models for routing")

    try:
        res = diagnose(proof, audit=True)
    except Exception:  # noqa: BLE001
        banner("DIAGNOSIS RAISED")
        traceback.print_exc()
        return 1

    d = res.diagnosis
    print(f"\n(model {res.model} · {res.tier} tier · {res.runtime} · {round(res.latency_ms)}ms)")
    banner("DIAGNOSIS")
    print("SUMMARY           :", d["summary"])
    print("MEANING           :", d["meaning"])
    if d["construction_brief"]:
        print("CONSTRUCTION BRIEF:", d["construction_brief"])
    for label, key in (("ANOMALIES", "anomalies"), ("CONFOUNDS", "confounds"),
                       ("RECOMMENDATIONS", "recommendations")):
        for item in d.get(key, []):
            print(f"  - {label[:-1].title()}: {item}")
    print("NEXT QUESTION     :", d["next_question"])

    if write:
        out = proof_path.parent / "diagnosis.json"
        out.write_text(json.dumps(res.to_dict(), indent=2), encoding="utf-8")
        print(f"\nwritten: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
