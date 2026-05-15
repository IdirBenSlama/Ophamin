"""Tightened Kimera throughput measurement -> the first real Empirical Proof Record.

Re-measures Kimera throughput properly: construction cost is separated from the
steady-state per-cycle cost, the entity is measured at a batch large enough to
amortise construction, and every target is run with and without the
GPU-acceleration flag. Stimuli are REAL corpus records (the offensive-security
corpus). Pre-registration is captured BEFORE any measurement runs.

The output is a signed Empirical Proof Record for the catastrophic-testing
feasibility claim — written to ``proofs/``.

    PYTHONPATH=src .venv/bin/python -u examples/measure_kimera_throughput.py
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

from ophamin import __version__
from ophamin.seeing.corpus import get_corpus
from ophamin.measuring.proof import (
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
    content_hash,
)
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
GPU_ENV = {"KIMERA_GPU_ACCELERATION_ENABLED": "1"}
PROOF_HOURS_THRESHOLD = 4.0
PROJECTED_RUN_CYCLES = 50_000
MAX_STIMULUS_CHARS = 4000
ENTITY_N = 15
COMPONENT_N = 40


def banner(text: str) -> None:
    print("\n" + "=" * 72 + "\n" + text + "\n" + "=" * 72)
    sys.stdout.flush()


def main() -> None:
    # --- real stimuli from a real corpus ----------------------------------
    corpus = get_corpus("cyber")  # the offensive-security corpus
    if not corpus.is_available():
        raise SystemExit("offensive-security corpus is not available")
    stimuli = [
        record.text[:MAX_STIMULUS_CHARS]
        for record in itertools.islice(corpus.records(), COMPONENT_N)
    ]
    dataset = corpus.dataset_ref()
    banner(f"stimuli: {len(stimuli)} real records from {dataset.name} "
           f"(content {dataset.content_hash[:16]})")

    # --- PRE-REGISTRATION (captured BEFORE any measurement) ---------------
    measurement_config = {
        "repo": REPO,
        "projected_run_cycles": PROJECTED_RUN_CYCLES,
        "threshold_hours": PROOF_HOURS_THRESHOLD,
        "entity_n": ENTITY_N,
        "component_n": COMPONENT_N,
        "gpu_env": GPU_ENV,
        "max_stimulus_chars": MAX_STIMULUS_CHARS,
    }
    prereg = PreRegistration(
        config_hash=content_hash(measurement_config),
        data_hash=dataset.content_hash,
        analysis_plan=(
            "Measure steady-state cycles/sec (construction separated from per-cycle "
            "cost) for the Kimera entity and two cheap components, each with and "
            "without the GPU-acceleration flag, on real offensive-security corpus "
            f"stimuli truncated to {MAX_STIMULUS_CHARS} chars. Project the fastest "
            f"component's steady-state rate to a {PROJECTED_RUN_CYCLES}-cycle run and "
            f"compare against the {PROOF_HOURS_THRESHOLD}h threshold."
        ),
        sweep_grid={"target": ["entity", "arachne", "rosetta"], "gpu": [False, True]},
    )

    # --- MEASURE ----------------------------------------------------------
    measurements: dict[str, dict] = {}

    def measure(label: str, target: str, n: int, env: dict | None) -> None:
        banner(f"measure {label}  (target={target} n={n} gpu={'on' if env else 'off'})")
        adapter = KimeraAdapter(REPO, target=target, mode="batch", env=env)
        result = adapter.measure_throughput(stimuli[:n])
        print(json.dumps(result, indent=1))
        sys.stdout.flush()
        measurements[label] = result

    measure("entity_cpu", "entity", ENTITY_N, None)
    measure("entity_gpu", "entity", ENTITY_N, GPU_ENV)
    measure("arachne_cpu", "arachne", COMPONENT_N, None)
    measure("arachne_gpu", "arachne", COMPONENT_N, GPU_ENV)
    measure("rosetta_cpu", "rosetta", COMPONENT_N, None)

    # --- VERDICT: project the fastest component steady-state to 50k cycles
    component_rates = [
        m["steady_state_cycles_per_sec"]
        for label, m in measurements.items()
        if m.get("ok")
        and label.startswith(("arachne", "rosetta"))
        and m["steady_state_cycles_per_sec"] > 0
    ]
    best_rate = max(component_rates) if component_rates else 0.0
    projected_hours = (
        PROJECTED_RUN_CYCLES / best_rate / 3600.0 if best_rate > 0 else 1.0e9
    )

    threshold = Threshold(
        "projected_50k_component_run_hours", "<=", PROOF_HOURS_THRESHOLD, "hours"
    )
    claim = Claim(
        statement=(
            f"A {PROJECTED_RUN_CYCLES:,}-cycle component-level catastrophic run against "
            f"Kimera-SWM completes within {PROOF_HOURS_THRESHOLD} hours on this vessel."
        ),
        operationalization=(
            "measured steady-state cycles/sec (construction excluded) of the fastest "
            f"component target, projected to {PROJECTED_RUN_CYCLES} cycles"
        ),
        threshold=threshold,
        h0=f"projected run time > {PROOF_HOURS_THRESHOLD}h — in-session density testing impractical",
        h1=f"projected run time <= {PROOF_HOURS_THRESHOLD}h — in-session density testing is practical",
    )
    verdict = Verdict.decide(projected_hours, threshold)

    # --- EVIDENCE ---------------------------------------------------------
    evidence = []
    for label, m in measurements.items():
        if not m.get("ok"):
            evidence.append(
                PillarEvidence(
                    pillar=f"throughput.{label}",
                    statistic_name="steady_state_cycles_per_sec",
                    statistic_value=0.0,
                    library="ophamin",
                    library_version=__version__,
                    cross_check="failed",
                    detail={"error": m.get("error", "measurement failed")},
                )
            )
            continue
        evidence.append(
            PillarEvidence(
                pillar=f"throughput.{label}",
                statistic_name="steady_state_cycles_per_sec",
                statistic_value=m["steady_state_cycles_per_sec"],
                library="ophamin",
                library_version=__version__,
                cross_check="n/a",
                detail={
                    "target": m["target"],
                    "n": m["n"],
                    "gross_cycles_per_sec": m["gross_cycles_per_sec"],
                    "construct_seconds": m["construct_seconds"],
                    "median_cycle_seconds": m["median_cycle_seconds"],
                    "mean_cycle_seconds": m["mean_cycle_seconds"],
                    "wall_seconds": m["wall_seconds"],
                    "succeeded": m.get("succeeded"),
                    "gpu_enabled": bool(m.get("env")),
                },
            )
        )

    git_commit = KimeraAdapter(REPO, target="entity").git_commit()
    record = EmpiricalProofRecord(
        claim=claim,
        preregistration=prereg,
        datasets=[dataset],
        substrate_name="kimera-swm",
        substrate_git_commit=git_commit,
        evidence=evidence,
        verdict=verdict,
        reproduction=Reproduction(
            command="PYTHONPATH=src .venv/bin/python -u examples/measure_kimera_throughput.py",
        ),
        provenance={"entity": {}, "activity": {}, "agent": {}},
        ophamin_version=__version__,
    )
    record.sign(b"ophamin-throughput-proof-key")

    out_dir = Path("proofs")
    out_dir.mkdir(exist_ok=True)
    short = record.proof_id[:16]
    record.to_json(str(out_dir / f"throughput_{short}.json"))
    record.to_markdown(str(out_dir / f"throughput_{short}.md"))

    banner("THROUGHPUT EMPIRICAL PROOF RECORD")
    print(record.to_markdown())
    problems = record.validate()
    print(f"\nvalidate(): {'WELL-FORMED' if not problems else problems}")
    print(f"signature verifies: {record.verify_signature(b'ophamin-throughput-proof-key')}")
    print(f"\nwritten: proofs/throughput_{short}.json  +  .md")


if __name__ == "__main__":
    main()
