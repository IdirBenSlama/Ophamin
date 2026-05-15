"""Run the Rosetta Scaling scenario against real Kimera-SWM.

Streams sentence-aligned FLORES-200 translations through Kimera's Rosetta
layer (``RosettaStele.process``) and measures whether the universal-semantic-
address promise holds across N languages — every language for the same
sentence should collapse to one canonical address.

A REFUTED verdict (Rosetta is encoder-fallback-dominated outside its ~54-entry
UNIVERSAL_REGISTRY) is the framework working: it surfaces the gap between the
blueprint promise and the registry-bound implementation.

    PYTHONPATH=src .venv/bin/python -u examples/run_rosetta_scaling.py
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ophamin.scenario import RosettaScalingScenario
from ophamin.scenario.base import DEFAULT_SIGN_KEY
from ophamin.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
N_CYCLES = 1000             # 20 sentence groups × 50 langs/group
K_MAX = 50
PRIMARY_K = 10
AGREEMENT_THRESHOLD = 0.80  # Rosetta's own blueprint promise
SEED = 0
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — CATASTROPHIC SCENARIO #2: ROSETTA SCALING")
    print(
        f"Claim under test: across {K_MAX} randomly-sampled language translations of "
        f"the same sentence, Kimera's Rosetta returns ONE canonical address in "
        f">= {AGREEMENT_THRESHOLD:.0%} of sentence groups at K={PRIMARY_K}."
    )
    print("A REFUTED verdict is the framework working — it names a real debt.")

    # 1h batch timeout — incremental-emit runner salvages cycles on timeout
    substrate = KimeraAdapter(
        REPO, target="rosetta", mode="batch", batch_timeout=3600.0
    )
    scenario = RosettaScalingScenario(
        n_cycles=N_CYCLES,
        k_max=K_MAX,
        primary_k=PRIMARY_K,
        agreement_threshold=AGREEMENT_THRESHOLD,
        seed=SEED,
    )
    print(f"corpus    : {scenario.corpus_name} (FLORES-200 aligned)")
    print(f"substrate : {substrate.name} @ {substrate.git_commit()[:12]}")
    print(f"target    : rosetta  ({substrate.metadata()['target_class']})")
    print(f"streaming : {N_CYCLES} cycles = {N_CYCLES // K_MAX} groups × {K_MAX} langs ...")

    try:
        record = scenario.run(substrate, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("ROSETTA SCALING RAISED")
        traceback.print_exc()
        return 1

    OUT_DIR.mkdir(exist_ok=True)
    short = record.proof_id[:16]
    json_path = OUT_DIR / f"rosetta_scaling_{short}.json"
    md_path = OUT_DIR / f"rosetta_scaling_{short}.md"
    record.to_json(str(json_path))
    record.to_markdown(str(md_path))

    print(record.to_markdown())
    problems = record.validate()
    sig_ok = record.verify_signature(DEFAULT_SIGN_KEY)
    print(f"\nvalidate()        : {'WELL-FORMED' if not problems else problems}")
    print(f"signature verifies: {sig_ok}")
    print(f"written           : {json_path}")
    print(f"                    {md_path}")

    canonical_ev = next(
        e for e in record.evidence
        if e.statistic_name.startswith("rosetta_canonical_agreement_at_k")
    )
    prime_ev = next(
        e for e in record.evidence
        if e.statistic_name.startswith("rosetta_prime_agreement_at_k")
    )

    banner("PER-K REPORT")
    per_k = canonical_ev.detail.get("per_k", {})
    print(f"{'K':>4}  {'n_groups':>9}  {'canonical_agree':>16}  {'prime_agree':>12}")
    print("-" * 50)
    # per_k keys may be strings or ints depending on JSON round-trip; coerce
    for k in sorted(per_k.keys(), key=lambda x: int(x)):
        row = per_k[k]
        print(
            f"{int(k):>4}  {row['n_groups']:>9}  "
            f"{row['canonical_rate']:>15.1%}  {row['prime_rate']:>11.1%}"
        )

    banner("VERDICT")
    print(f"target      : rosetta")
    print(f"verdict     : {record.verdict.outcome}")
    print(f"observed    : {canonical_ev.statistic_value:.1%} canonical at K={PRIMARY_K}")
    print(f"             (prime: {prime_ev.statistic_value:.1%})")
    print(f"reasoning   : {record.verdict.reasoning}")
    print(f"proof       : {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
