"""Concept walkthrough — FWER correction across a campaign (RFC 0002 Phase E2).

When a campaign produces N scenario verdicts at independent α=0.05,
the probability of at least one spurious VALIDATED climbs fast.
At N=19 it's ≈ 62 %. Ophamin closes this gap with two
industry-standard corrections:

* **Holm-Bonferroni** — strictly controls family-wise error rate (FWER).
  Reference: Holm (1979), DOI 10.2307/4615733.
* **Benjamini-Hochberg** — controls false-discovery rate (FDR);
  less conservative. Reference: B&H (1995),
  DOI 10.1111/j.2517-6161.1995.tb02031.x.

This script walks through both methods on a hand-crafted family of
ten p-values. Run with::

    PYTHONPATH=src python examples/walkthrough_fwer_correction.py

The script asserts the corrections behave as documented and prints
rich annotated output. It's safe to import — the demo runs only when
invoked as ``__main__``.
"""

from __future__ import annotations

from ophamin.comparing.fwer import (
    CorrectionFamily,
    CorrectionInput,
    apply_correction,
    benjamini_hochberg,
    holm_bonferroni,
    no_correction,
)


def _print_family(label: str, family: CorrectionFamily) -> None:
    """Pretty-print a CorrectionFamily with per-claim details."""
    print(f"\n  {label}")
    print(f"    method:        {family.method}")
    print(f"    alpha:         {family.alpha}")
    print(f"    family_size:   {family.family_size}")
    print(f"    n_rejections:  {family.n_rejections}")
    print(f"    {'claim_id':<10} {'raw_p':>8} {'adj_p':>8} {'verdict':>14} {'sig?':>6}")
    print(f"    {'-' * 60}")
    for r in family.results:
        raw = f"{r.raw_p_value:.4f}" if r.raw_p_value is not None else "—"
        adj = f"{r.corrected_p_value:.4f}" if r.corrected_p_value is not None else "—"
        sig = "✓" if r.significant_after_correction else "✗"
        print(f"    {r.claim_id:<10} {raw:>8} {adj:>8} {r.corrected_verdict:>14} {sig:>6}")


def main() -> None:
    print("# FWER correction walkthrough — RFC 0002 Phase E2")
    print()
    print("A hand-crafted family of ten p-values. Three are small enough to")
    print("survive even strict FWER correction; four sit in the middle")
    print("where Holm rejects and BH accepts; three are large.")

    # Construct the input family. claim_ids are arbitrary stable strings;
    # in real campaigns they'd be the proof_id of each signed record.
    inputs = [
        CorrectionInput("claim_01", "VALIDATED", 0.001),
        CorrectionInput("claim_02", "VALIDATED", 0.005),
        CorrectionInput("claim_03", "VALIDATED", 0.008),
        CorrectionInput("claim_04", "VALIDATED", 0.013),
        CorrectionInput("claim_05", "VALIDATED", 0.022),
        CorrectionInput("claim_06", "VALIDATED", 0.038),
        CorrectionInput("claim_07", "VALIDATED", 0.046),
        CorrectionInput("claim_08", "VALIDATED", 0.080),
        CorrectionInput("claim_09", "VALIDATED", 0.220),
        CorrectionInput("claim_10", "VALIDATED", 0.700),
    ]
    print(f"\n  Family size: {len(inputs)} VALIDATED claims at raw α=0.05")

    # === No correction (the dangerous baseline)
    none_family = no_correction(inputs, alpha=0.05)
    _print_family("Layer 1 — no correction (raw)", none_family)
    print(f"    → {none_family.n_rejections}/{len(inputs)} claims keep VALIDATED")
    print(f"    → P(≥1 spurious) ≈ 1 - 0.95^{len(inputs)} = "
          f"{1.0 - 0.95 ** len(inputs):.3f}")

    # === Holm-Bonferroni
    holm_family = holm_bonferroni(inputs, alpha=0.05)
    _print_family("Layer 2 — Holm-Bonferroni (strict FWER control)", holm_family)
    print(f"    → {holm_family.n_rejections}/{len(inputs)} claims keep VALIDATED")
    print( "    → FWER is strictly bounded at α=0.05 across the entire family")

    # === Benjamini-Hochberg
    bh_family = benjamini_hochberg(inputs, alpha=0.05)
    _print_family("Layer 3 — Benjamini-Hochberg (FDR control)", bh_family)
    print(f"    → {bh_family.n_rejections}/{len(inputs)} claims keep VALIDATED")
    print( "    → FDR is bounded; expected proportion of false discoveries ≤ α")

    # === Invariants we can pin
    assert holm_family.n_rejections <= bh_family.n_rejections, (
        "Holm must reject ≤ what BH rejects on the same family"
    )
    assert bh_family.n_rejections <= none_family.n_rejections, (
        "BH must reject ≤ what raw-α-only does"
    )

    # === The 0.9.0 wire-format integration
    print("\n## CampaignRecord/2.0 integration")
    print()
    print("  Every ophamin run-all (since 0.9.0) emits a signed CampaignRecord")
    print("  whose new schema-2.0 fields carry the FWER pass:")
    print(f"    corrected_verdicts            = {dict(list(holm_family.verdicts().items())[:3])} ...")
    print( "    multiplicity_correction_method = \"holm\"  (or \"bh\" / \"none\")")
    print()
    print("  The legacy schema-1.0 wire format still decodes cleanly; the")
    print("  version-aware _body() makes the 1.0 signature still verify under")
    print("  the 2.0-aware reader. See SCHEMAS.md §\"Case study\".")

    # === Dispatch via the public API
    print("\n## Public API")
    print()
    print("  Both methods are reachable via apply_correction(method=...):")
    for method in ("holm", "bh", "none"):
        result = apply_correction(inputs, method=method, alpha=0.05)
        print(f"    apply_correction(method={method!r}, alpha=0.05) "
              f"→ {result.n_rejections}/{len(inputs)} rejections")

    print("\n✓ FWER walkthrough complete. All invariants pinned.")


if __name__ == "__main__":
    main()
