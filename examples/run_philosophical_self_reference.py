"""Run the Philosophical Self-Reference scenario against real Kimera-SWM.

The third experimentation tier landing: pre-registers a Cohen's d effect
size on dissonance_events_count between self-referential and neutral text.
A REFUTED verdict says Kimera's substrate does not differentially process
content about itself; a VALIDATED verdict pins a self-recognition signal.

    PYTHONPATH=src .venv/bin/python -u examples/run_philosophical_self_reference.py
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ophamin.measuring.scenarios import PhilosophicalSelfReferenceScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
N_SELF_REF = 30
N_NEUTRAL = 30
EFFECT_SIZE_THRESHOLD = 0.30   # small-to-medium effect per Cohen 1988
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — PHILOSOPHICAL-TIER SCENARIO: SELF-REFERENCE")
    print(
        f"Claim under test: when fed text describing Kimera's own primitives, "
        f"the substrate produces a measurably different dissonance signal "
        f"than on neutral text — Cohen's d >= {EFFECT_SIZE_THRESHOLD:.2f} "
        f"(one-sided, self-referential > neutral)."
    )
    print("A REFUTED verdict says the substrate does NOT differentially "
          "process content about itself.")

    adapter = KimeraAdapter(
        REPO, target="entity", mode="batch", batch_timeout=1800.0
    )
    scenario = PhilosophicalSelfReferenceScenario(
        effect_size_threshold=EFFECT_SIZE_THRESHOLD,
        n_self_ref=N_SELF_REF,
        n_neutral=N_NEUTRAL,
    )
    print(f"corpus    : {scenario.corpus_name} (neutral baseline)")
    print(f"bundled   : {N_SELF_REF} self-referential sentences (CLAUDE.md-derived)")
    print(f"substrate : {adapter.name} @ {adapter.git_commit()[:12]}")
    print(f"target    : entity  ({adapter.metadata()['target_class']})")
    print(f"streaming : {N_SELF_REF + N_NEUTRAL} total cycles (may take ~1-3 min)")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("PHILOSOPHICAL SELF-REFERENCE RAISED")
        traceback.print_exc()
        return 1

    OUT_DIR.mkdir(exist_ok=True)
    short = record.proof_id[:16]
    json_path = OUT_DIR / f"philosophical_self_reference_{short}.json"
    md_path = OUT_DIR / f"philosophical_self_reference_{short}.md"
    record.to_json(str(json_path))
    record.to_markdown(str(md_path))

    primary = next(
        e for e in record.evidence
        if e.statistic_name == "dissonance_cohens_d_self_ref_vs_neutral"
    )
    mwu = next(
        e for e in record.evidence
        if e.statistic_name == "dissonance_mannwhitneyu_p_value"
    )
    sr = next(
        e for e in record.evidence
        if e.statistic_name == "self_ref_dissonance_median"
    )
    nu = next(
        e for e in record.evidence
        if e.statistic_name == "neutral_dissonance_median"
    )

    banner("DISSONANCE DISTRIBUTIONS BY GROUP")
    sr_dist = sr.detail["distribution"]
    nu_dist = nu.detail["distribution"]
    print(f"  self_ref : n={sr_dist['n']}  "
          f"median={sr_dist['median']:.1f}  mean={sr_dist['mean']:.2f}  "
          f"range=[{sr_dist['min']:.0f}, {sr_dist['max']:.0f}]")
    print(f"  neutral  : n={nu_dist['n']}  "
          f"median={nu_dist['median']:.1f}  mean={nu_dist['mean']:.2f}  "
          f"range=[{nu_dist['min']:.0f}, {nu_dist['max']:.0f}]")

    banner("STATISTICAL TESTS")
    print(f"  Cohen's d (self_ref - neutral)/pooled_sd : {primary.statistic_value:+.3f}")
    print(f"  threshold                                 : >= {EFFECT_SIZE_THRESHOLD:.2f}")
    if mwu.p_value is not None:
        u = mwu.detail["u_statistic"]
        print(f"  Mann-Whitney U                            : {u:.1f}")
        print(f"  one-sided p-value                         : {mwu.p_value:.4f}")

    banner("VERDICT")
    print(f"verdict     : {record.verdict.outcome}")
    print(f"observed    : Cohen's d = {primary.statistic_value:+.3f}")
    print(f"reasoning   : {record.verdict.reasoning}")
    print(f"proof       : {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
