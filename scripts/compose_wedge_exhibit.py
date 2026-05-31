#!/usr/bin/env python
"""Compose the Memory Wedge exhibit — one world-facing, self-contained package
from the two signed mechanism proofs.

It does NOT re-measure or re-render anything substantive: it gathers the existing
signed proof bundles (their own proof.html), re-verifies each signature, emits a
DSSE in-toto attestation per proof, and writes a narrative `index.html` that puts
the two proofs in plain language with their real numbers + honest caveats. The
result is a directory you can zip and hand to anyone.

Usage:  .venv/bin/python scripts/compose_wedge_exhibit.py
"""
from __future__ import annotations

import html
import json
import shutil
from glob import glob
from pathlib import Path

from ophamin.interop import to_dsse_envelope
from ophamin.measuring.proof.record import EmpiricalProofRecord
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY

EXHIBIT = Path("exhibits/wedge_memory_2026-05-31")

# The two proofs, newest bundle of each, + the plain-language framing for each.
PROOFS = [
    {
        "glob": "proofs/scientific/scar-accumulation-flow/2026-05-31_*/proof.json",
        "headline": "Memory is physical — it accumulates, and never resets.",
        "plain": (
            "We showed Kimera eight ideas, twice each, with other experience in "
            "between. Every time, the manifold it lives on was measurably more "
            "deformed than before, and the deformation never once dropped. Memory "
            "here is not a stored string — it is a permanent physical change to the "
            "substrate, which we read straight off the live engine and signed."
        ),
        "caveat": (
            "The deformation grew uniformly (≈ one scar per cycle), so this proves "
            "the no-reset / accumulation law cleanly — not yet a history-conditioned "
            "magnitude. The richer geometry (the geoid) does move; scoring it is next."
        ),
    },
    {
        "glob": "proofs/scientific/memory-order-hysteresis/2026-05-31_refuted_*/proof.json",
        "headline": "Is memory order-dependent? Tested harder — REFUTED.",
        "plain": (
            "At six probes this looked striking: the same question after a different "
            "document order gave a fully divergent answer (1.0), while a RAG retriever "
            "stayed order-blind (0.0). Widening to fifteen probes broke it. The control "
            "— running the <i>same</i> order twice — also diverged fully (noise-floor "
            "1.0), which means Kimera's prime-address is not reproducible run-to-run at "
            "this scale. So the order-effect cannot be separated from run noise: "
            "order_hysteresis collapsed to 0.0. The small-sample result did not replicate."
        ),
        "caveat": (
            "This is the proof doing its job. The open question it surfaces is "
            "foundational and bigger than this claim: is the substrate non-deterministic "
            "run-to-run (a seeding issue), or is the prime-chain fingerprint too brittle? "
            "Settling that is the next step — not salvaging this claim."
        ),
    },
]

THESIS = (
    "Kimera-SWM is a non-LLM, physics-based intelligence. These are two falsifiable "
    "measurements of its <b>memory</b>, taken from the live substrate and "
    "cryptographically signed. One <b>held</b> under stronger testing; one was "
    "<b>refuted</b> when the sample was widened — and the refutation is signed too. "
    "That is the point of this layer: metrology you can trust <i>because</i> it "
    "falsifies itself, not a dashboard that only ever agrees with you."
)

WHY = (
    "The first proof reads a physical change to an owned substrate — a scar an LLM "
    "stack has no equivalent of, because it owns no accumulating manifold to measure. "
    "The second proof matters for a different reason: a marketing dashboard never "
    "reports that its own earlier result failed to replicate. This layer does, and "
    "signs the failure. The wedge is not any single claim — it is owning a mechanism "
    "you can measure, sign, reproduce, and <i>refute</i>."
)

HONEST = (
    "These proofs establish the <b>legibility wedge</b> — that Ophamin can see, sign, "
    "and reproduce Kimera's mechanism. They do <b>not</b> claim Kimera out-thinks any "
    "other system; that is a separate, open question. Read them as early, falsifiable, "
    "signed measurements — verdicts that could have come back REFUTED and did not."
)


def _newest(pattern: str) -> Path:
    matches = sorted(glob(pattern))
    if not matches:
        raise SystemExit(f"no proof matched: {pattern}")
    return Path(matches[-1])


def _stat(proof: EmpiricalProofRecord) -> tuple[str, str]:
    ev = proof.evidence[0]
    return ev.statistic_name, f"{ev.statistic_value:.4f}"


def _card(spec: dict, proof: EmpiricalProofRecord, verified: bool, rel_html: str) -> str:
    name = proof.evidence[0].pillar.split(".")[-1] if proof.evidence else ""
    stat_name, stat_val = _stat(proof)
    sig = ("✓ signature verified" if verified else "✗ SIGNATURE INVALID")
    sig_cls = "ok" if verified else "bad"
    return f"""
    <section class="card">
      <div class="verdict {proof.verdict.outcome.lower()}">{html.escape(proof.verdict.outcome)}</div>
      <h2>{html.escape(spec['headline'])}</h2>
      <p class="plain">{spec['plain']}</p>
      <table class="kv">
        <tr><td>scenario</td><td class="mono">{html.escape(getattr(proof, 'scenario_name', '') or name)}</td></tr>
        <tr><td>primary statistic</td><td class="mono">{html.escape(stat_name)} = {stat_val}</td></tr>
        <tr><td>proof id</td><td class="mono">{html.escape(proof.proof_id[:32])}…</td></tr>
        <tr><td>signature</td><td class="{sig_cls}">{sig}</td></tr>
      </table>
      <p class="caveat"><b>Honest caveat.</b> {spec['caveat']}</p>
      <a class="btn" href="{rel_html}">Open the full signed proof →</a>
    </section>"""


def main() -> None:
    if EXHIBIT.exists():
        shutil.rmtree(EXHIBIT)
    (EXHIBIT / "proofs").mkdir(parents=True)

    cards: list[str] = []
    manifest: dict = {"title": "Kimera-SWM — The Memory Wedge", "proofs": []}
    for spec in PROOFS:
        pjson = _newest(spec["glob"])
        bundle = pjson.parent
        proof = EmpiricalProofRecord.from_dict(json.loads(pjson.read_text()))
        verified = proof.verify_signature(DEFAULT_SIGN_KEY)

        dest = EXHIBIT / "proofs" / bundle.name
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pjson, dest / "proof.json")
        if (bundle / "proof.html").exists():
            shutil.copy2(bundle / "proof.html", dest / "proof.html")
        # machine-verifiable DSSE in-toto attestation alongside the proof
        envelope = to_dsse_envelope(proof, DEFAULT_SIGN_KEY)
        (dest / "proof.intoto.json").write_text(
            json.dumps(envelope, indent=2, sort_keys=True)
        )

        rel_html = f"proofs/{bundle.name}/proof.html"
        cards.append(_card(spec, proof, verified, rel_html))
        sn, sv = _stat(proof)
        manifest["proofs"].append({
            "scenario": getattr(proof, "scenario_name", "") or bundle.name,
            "proof_id": proof.proof_id,
            "verdict": proof.verdict.outcome,
            "statistic": {sn: sv},
            "signature_verified": verified,
            "bundle": rel_html,
            "attestation": f"proofs/{bundle.name}/proof.intoto.json",
        })

    page = _PAGE.format(thesis=THESIS, cards="\n".join(cards), why=WHY, honest=HONEST)
    (EXHIBIT / "index.html").write_text(page, encoding="utf-8")
    (EXHIBIT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"exhibit written: {EXHIBIT}/index.html")
    for p in manifest["proofs"]:
        print(f"  · {p['scenario']}: {p['verdict']} "
              f"({list(p['statistic'].items())[0]}) sig={p['signature_verified']}")


_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kimera-SWM — The Memory Wedge</title>
<style>
  :root {{ --bg:#0e1116; --panel:#161b22; --line:#2b3340; --txt:#d6deeb;
          --muted:#8b98a9; --acc:#6ad1c0; --ok:#3fb950; --bad:#f85149; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--txt);
          font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif; }}
  .wrap {{ max-width:820px; margin:0 auto; padding:48px 22px 80px; }}
  h1 {{ font-size:30px; margin:0 0 6px; letter-spacing:-.02em; }}
  .sub {{ color:var(--muted); margin:0 0 28px; }}
  .lead {{ font-size:17px; background:var(--panel); border:1px solid var(--line);
           border-left:3px solid var(--acc); border-radius:10px; padding:18px 20px; }}
  .card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px;
           padding:22px 24px; margin:22px 0; }}
  .card h2 {{ font-size:20px; margin:6px 0 10px; }}
  .verdict {{ display:inline-block; font:600 11px/1 ui-monospace,monospace;
              letter-spacing:.08em; padding:5px 9px; border-radius:6px; }}
  .verdict.validated {{ color:var(--ok); background:rgba(63,185,80,.12);
                        border:1px solid rgba(63,185,80,.4); }}
  .verdict.refuted {{ color:var(--bad); background:rgba(248,81,73,.12);
                      border:1px solid rgba(248,81,73,.4); }}
  .plain {{ color:var(--txt); }}
  .caveat {{ color:var(--muted); font-size:13.5px; border-top:1px solid var(--line);
             padding-top:12px; }}
  table.kv {{ width:100%; border-collapse:collapse; margin:14px 0; }}
  table.kv td {{ padding:5px 0; border-bottom:1px solid var(--line); font-size:13.5px;
                 vertical-align:top; }}
  table.kv td:first-child {{ color:var(--muted); width:160px; }}
  .mono {{ font-family:ui-monospace,SFMono-Regular,monospace; font-size:12.5px; }}
  .ok {{ color:var(--ok); }} .bad {{ color:var(--bad); font-weight:600; }}
  .btn {{ display:inline-block; margin-top:8px; color:var(--acc);
          text-decoration:none; font-size:13.5px; }}
  .btn:hover {{ text-decoration:underline; }}
  .note {{ background:var(--panel); border:1px solid var(--line); border-radius:10px;
           padding:16px 20px; margin:22px 0; }}
  .note h3 {{ font-size:14px; margin:0 0 8px; color:var(--acc);
              text-transform:uppercase; letter-spacing:.06em; }}
  footer {{ color:var(--muted); font-size:12px; margin-top:36px;
            border-top:1px solid var(--line); padding-top:16px; }}
</style></head><body><div class="wrap">
  <h1>The Memory Wedge</h1>
  <p class="sub">Two signed proofs from Kimera-SWM — measured on the live substrate.</p>
  <div class="lead">{thesis}</div>
  {cards}
  <div class="note"><h3>Why no LLM or RAG stack can produce these</h3><p>{why}</p></div>
  <div class="note"><h3>What these do and do not claim</h3><p>{honest}</p></div>
  <div class="note"><h3>Verify it yourself</h3><p>Each proof carries an HMAC signature
    (re-checked when this page was built) and a DSSE in-toto attestation
    (<span class="mono">proof.intoto.json</span>). The proof JSON is content-addressed:
    its <span class="mono">proof_id</span> is a SHA-256 over the claim + pre-registration
    + evidence, so any edit breaks both the id and the signature.</p></div>
  <footer>Generated by Ophamin — the legibility layer for Kimera-SWM. Each proof was
    produced by running the named scenario against live Kimera and signing the result.
    This page re-renders existing signed bundles; it measures nothing new.</footer>
</div></body></html>"""


if __name__ == "__main__":
    main()
