# Reproducer — Concentrated Immune Siege (GWF false-positive ceiling)

> **What this doc is**: a step-by-step walkthrough for an external
> reviewer who wants to (a) verify the 8 shipped `immune_siege_*`
> proofs, (b) understand why both `VALIDATED` and `REFUTED` proofs
> co-exist for the same claim, and (c) re-run the scenario against
> their own Kimera-SWM check-out.
>
> **Time to verify**: ~30 seconds (signature checks only, no run).
> **Time to spot-check re-run**: ~2 minutes (n_cycles=100, sample
> corpus). **Time to full re-run**: ~15-30 minutes per setup
> (1000 cycles, full corpus subset).

## 1. The pre-registered claim

Every `immune_siege_*` proof in [`proofs/`](..) pre-registers the
**same** five-tuple:

| Field | Value |
|---|---|
| `metric` | `gwf_false_positive_rate` |
| `comparator` | `<=` |
| `value` | `0.1` (10 %) |
| `H0` | GWF false-positive rate `> 0.1` |
| `H1` | GWF false-positive rate `<= 0.1` |

In plain terms: under a concentrated immune siege of labelled
adversarial inputs, Kimera's Gyroscopic Water Fortress (GWF) is
claimed to block **no more than 10 %** of benign inputs.

The verdict is computed mechanically by
`Threshold.decide(observed)` (`record.py:113`); the experimenter
cannot vote on the outcome. The threshold (10 %) is the
architectural false-positive ceiling Kimera's design document
names — not a value chosen post-hoc to make the proof pass.

## 2. Why **8 proofs**, **3 different verdicts**

The 8 shipped proofs split into three experimental setups by
**target arm** + **cycle execution**:

| Setup | Target | Count | Verdict | Observed FP |
|---|---|---|---|---|
| **A — full pipeline** | `entity` (Takwin's normal cognitive pipeline) | 3 | `VALIDATED` | 3.2 % (16/500) |
| **B — direct GWF** | `gwf` (bypass Takwin, hit GWF directly) | 4 | `REFUTED` | 100 % (500/500) |
| **C — adapter error** | `entity` | 1 | `INCONCLUSIVE` | 0 % (0/4343 — substrate not exercised) |

**Setup A** (entity-target, VALIDATED):

| Proof file | Kimera commit |
|---|---|
| [`immune_siege_entity_0a0575db92c0dcf5.json`](../immune_siege_entity_0a0575db92c0dcf5.json) | `9596c681…` |
| [`immune_siege_entity_6d47d8c9a2deef83.json`](../immune_siege_entity_6d47d8c9a2deef83.json) | `4552de7e…` |
| [`immune_siege_entity_d030c48f4d6f5534.json`](../immune_siege_entity_d030c48f4d6f5534.json) | `9c055d30…` |

GWF runs **inside** Takwin's full defense stack (GWF +
manipulation-detector + Danger-Theory-Gate). The full stack
catches 54.2-54.4 % of malicious inputs at 15.6-15.8 % overall
FP cost; the GWF-only contribution to that FP is 3.2 % — under
the 10 % ceiling. Three independent Kimera commits all reproduce
the 3.2 % rate, so the claim is **robust across Kimera versions**.

**Setup B** (gwf-direct, REFUTED):

| Proof file | Kimera commit |
|---|---|
| [`immune_siege_gwf_027ace2fba81b68e.json`](../immune_siege_gwf_027ace2fba81b68e.json) | `9596c681…` |
| [`immune_siege_gwf_776d02f2497a8c0c.json`](../immune_siege_gwf_776d02f2497a8c0c.json) | `4552de7e…` |
| [`immune_siege_gwf_be023fabe6b17fbf.json`](../immune_siege_gwf_be023fabe6b17fbf.json) | `9c055d30…` |
| [`immune_siege_gwf_1f957bda52857b9a.json`](../immune_siege_gwf_1f957bda52857b9a.json) | `9596c681…` (7270-cycle variant) |

Bypassing Takwin and routing inputs directly through GWF, the
firewall blocks **100 %** of everything — both benign and
malicious. The FP rate of 1.0 is **10× over the threshold**, so
the claim is REFUTED. Same three Kimera commits as Setup A
reproduce this; the over-aggressive GWF behaviour is also robust.

**The empirical finding both setups produce together**: GWF in
isolation is **over-aggressive**; the **upstream Takwin cognitive
pipeline calibrates GWF down** to the architectural ceiling.
The framework's discipline surfaces this distinction rather than
hiding the REFUTED-direct-GWF result behind the VALIDATED-full-
pipeline one.

**Setup C** (adapter error, INCONCLUSIVE):

| Proof file | Kimera commit |
|---|---|
| [`immune_siege_entity_4f8a2ffd29ed0d7b.json`](../immune_siege_entity_4f8a2ffd29ed0d7b.json) | `9596c681…` |

7270 cycles, **7270 adapter errors** — the substrate never
actually executed any cycle. `INCONCLUSIVE` is the correct
verdict: substrate-not-exercised must never read as PASS. The
framework's adapter-error handling routes this to INCONCLUSIVE,
not VALIDATED with zero observations.

## 3. Verify a proof signature (no re-run needed)

Every shipped proof carries an HMAC-SHA256 signature over its
canonical body bytes. Verifying takes ~10 ms; no corpus, no
Kimera check-out, no run.

### Python (the framework's reference verifier)

```bash
# After `pip install -e ".[dev]"`:
ophamin schema validate proofs/immune_siege_entity_0a0575db92c0dcf5.json

# Or via the module directly (no install):
PYTHONPATH=src .venv/bin/python -m ophamin.cli schema validate \
    proofs/immune_siege_entity_0a0575db92c0dcf5.json
```

Expected output:

```
OK    proofs/immune_siege_entity_0a0575db92c0dcf5.json: proof@1.0

summary: 1 ok, 0 failed
```

### Rust (`ophamin-proof` crate, since 0.16.0)

```rust
use ophamin_proof::{parse_proof, verify_signature};
use std::fs;

let text = fs::read_to_string(
    "proofs/immune_siege_entity_0a0575db92c0dcf5.json",
)?;
let proof = parse_proof(&text)?;
let key = b"ophamin-scenario-proof-key";
assert!(verify_signature(&proof, key)?);
```

Or run the bundled example:

```bash
cd crates/ophamin-proof
cargo run --example verify_proof -- \
    ../../proofs/immune_siege_entity_0a0575db92c0dcf5.json
```

### JavaScript / TypeScript (`@ophamin/proof` package, since 0.16.0)

```typescript
import { readFileSync } from "node:fs";
import { parseProof, verifySignature } from "@ophamin/proof";

const text = readFileSync(
    "proofs/immune_siege_entity_0a0575db92c0dcf5.json",
    "utf-8",
);
const proof = parseProof(text);
const key = new TextEncoder().encode("ophamin-scenario-proof-key");
const ok = await verifySignature(proof, key);
console.log(ok ? "✓ verified" : "✗ FAILED");
```

Or run the bundled example after `npm run build`:

```bash
cd packages/ophamin-proof-js
npm run example:verify -- ../../proofs/immune_siege_entity_0a0575db92c0dcf5.json
```

**Cross-host invariant**: the same proof verifies bit-identically
under Python, Rust, and JS. If any one of the three reports
verification failure while the others pass, the wire-format
contract is broken — please file an issue.

## 4. Re-run the scenario (full corpus)

The canonical entry point is the bundled runner script — it
emits both the Setup A (entity-target) and Setup B (gwf-direct)
proofs in a single invocation:

```bash
PYTHONPATH=src .venv/bin/python -u examples/run_immune_siege.py
```

This produces two signed proof JSONs under `proofs/` per run —
one named `immune_siege_entity_<proof_id_prefix>.json` and one
named `immune_siege_gwf_<proof_id_prefix>.json`.

> **Caveat on the shipped proofs' §7 reproduction strings**: the
> shipped proofs were emitted in earlier framework versions whose
> CLI exposed `ophamin scenario <name>` as a direct runner. The
> current CLI's `ophamin scenario` is a list/show/info umbrella
> only; the runner moved to
> [`examples/run_immune_siege.py`](../../examples/run_immune_siege.py).
> The signatures verify regardless — the §7 string is historical
> metadata of how the proof was produced at the time, not a
> guarantee the same string still runs today. For the canonical
> entry-point, follow this section.
>
> **Update (0.29.0)**: the upstream emitter is fixed. Future
> proofs from this scenario family — and the other 5
> hand-rolled-runner scenarios (logic_topology_siege,
> organizational_dissonance, philosophical_self_reference,
> rosetta_scaling, throughput_ceiling) — now emit
> `PYTHONPATH=src .venv/bin/python -u examples/run_immune_siege.py`
> in their §7. See
> [`docs/proposals/PROOF_REPRODUCTION_COMMAND.md`](../../docs/proposals/PROOF_REPRODUCTION_COMMAND.md)
> for the partial-fix status + the wider 26-site follow-up.

**Hard-coded runner constants** (in
[`examples/run_immune_siege.py`](../../examples/run_immune_siege.py)):

- `REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM..."` — the
  Kimera-SWM checkout path. **External reviewers MUST edit this**
  to point at their own Kimera clone before running.
- `N_CYCLES = 1000` — the balanced-sample size. Reduce to e.g. 100
  for a spot-check (see §5 below).
- `FALSE_POSITIVE_CEILING = 0.10` — the threshold value (matches
  the architectural ceiling baked into the claim).

**Corpus requirements**:

- The scenario reads from the `offensive-security-corpus`
  (data hash `83109a27c3df2a45…`, 4,416,305 records). Sources:
  metasploit-framework, SecLists, PayloadsAllTheThings,
  nuclei-templates, atomic-red-team, exploit-db, garak, and
  prompt-injection / jailbreak sets.
- See [`src/ophamin/seeing/corpus/connectors.py:244+`](../../src/ophamin/seeing/corpus/connectors.py)
  for the canonical loader + the union-of-subcorpora logic
  (`OffensiveSecurityCorpus` class).
- The default scenario draws a 500-benign + 500-malicious
  balanced sample (1000 cycles). At full corpus size the run
  takes ~15-30 minutes on a modern laptop.

**Environment lock**: each shipped proof's §7 names
"Environment lock: 178 entries" — see
[`requirements-lock.darwin-py314.txt`](../../requirements-lock.darwin-py314.txt)
for the canonical pin. Per [`install.md`](../../docs/getting-started/install.md),
the lock file is **macOS Python 3.14 specific**; on Linux or
other Python versions, install from `pyproject.toml` directly
(fresh resolution).

## 5. Spot-check with a small subset

A fast smoke that exercises the same code paths without the full
15-30 minute run. Two approaches:

**(a) Edit the runner's `N_CYCLES`**

In [`examples/run_immune_siege.py`](../../examples/run_immune_siege.py)
change line 32:

```python
N_CYCLES = 100  # was 1000 — spot-check size
```

Then run as in §4. The spot-check completes in ~2 minutes.

**(b) Construct the scenario directly in Python**

```python
from ophamin.measuring.scenarios import ImmuneSiegeScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.seeing.substrate import KimeraAdapter

substrate = KimeraAdapter(
    "/path/to/your/Kimera-SWM",  # adjust
    target="entity",
    mode="batch",
)
scenario = ImmuneSiegeScenario(
    n_cycles=100,
    false_positive_ceiling=0.10,
    target="entity",
)
proof = scenario.run(substrate=substrate).sign(DEFAULT_SIGN_KEY)
print(f"verdict: {proof.verdict.outcome}")
print(f"observed: {proof.verdict.observed_value}")
```

**Expected behaviour**: a fresh proof with FP rate **in the same
neighbourhood** as the shipped 3.2 % (entity target) or 100 %
(gwf target). At n_cycles=100 the Wilson-CI width is ~10× wider
than the 1000-cycle run, so the point estimate may drift; the
**direction** of the verdict should still match.

If the spot-check produces a VALIDATED entity-target result and
a REFUTED gwf-target result that mirror the shipped proofs,
the substrate is behaving as the empirical record predicts.

## 6. Cross-proof diff

To compare a freshly-emitted proof against a shipped one:

```bash
# 1. Emit fresh proofs via the runner (writes two files to
#    proofs/ — one entity, one gwf; the filenames embed the
#    fresh proof_id so they don't collide with the shipped ones)
PYTHONPATH=src .venv/bin/python -u examples/run_immune_siege.py

# 2. Identify the fresh proofs (the most-recently-created
#    immune_siege_*.json files)
ls -t proofs/immune_siege_entity_*.json | head -1   # fresh entity
ls -t proofs/immune_siege_gwf_*.json    | head -1   # fresh gwf

# 3. Diff the verdict + evidence between a shipped and a fresh
#    proof (NOT the signature — signatures drift across runs
#    because §1's `created_at` timestamp differs)
PYTHONPATH=src .venv/bin/python -c "
import json, sys
shipped = json.load(open('proofs/immune_siege_entity_0a0575db92c0dcf5.json'))
fresh_path = sorted([p for p in __import__('glob').glob('proofs/immune_siege_entity_*.json') if '0a0575db' not in p])[-1]
fresh = json.load(open(fresh_path))

print('shipped verdict:', shipped['verdict']['outcome'])
print('fresh   verdict:', fresh['verdict']['outcome'])
print('shipped observed:', shipped['verdict']['observed_value'])
print('fresh   observed:', fresh['verdict']['observed_value'])
print('verdict-match:', shipped['verdict']['outcome'] == fresh['verdict']['outcome'])
"
```

**Stability claims**:
- `verdict.outcome` should match across re-runs (the framework's
  determinism is pinned by
  [`tests/test_framework_wide_reproducibility.py`](../../tests/test_framework_wide_reproducibility.py)).
- `verdict.observed_value` should match **exactly** for a given
  `(seed, corpus_hash, target)` triple; differs if any input changes.
- `proof_id` and `signature` change every run (the timestamp
  in §1 makes them content-distinct).

## 7. What this proof family demonstrates about Ophamin

The 8 immune_siege proofs are an illustrative microcosm of the
framework's discipline:

1. **Pre-registration is compulsory.** Every proof carries the
   same five-tuple. The threshold (10 %) is the architectural
   ceiling Kimera's design names — not a number chosen to make
   the proof pass.
2. **The verdict is mechanical.** `Threshold.decide(0.032) → True`
   produces VALIDATED; `Threshold.decide(1.0) → False` produces
   REFUTED. No experimenter judgement.
3. **REFUTED proofs ship alongside VALIDATED ones.** The
   gwf-direct REFUTED proofs reveal that GWF in isolation is
   over-aggressive — an honest finding that the framework's
   discipline surfaces rather than hides.
4. **Cross-commit robustness is structurally visible.** Each
   verdict reproduces across 3 distinct Kimera commits; the
   framework's discipline lets you see at a glance that the
   findings are not version-fragile.
5. **Adapter errors route to INCONCLUSIVE, not VALIDATED.** The
   one INCONCLUSIVE proof in this family carries 7270 adapter
   errors — substrate-not-exercised must never read as PASS.

## See also

- [`proofs/INDEX.md`](../INDEX.md) — full catalogue of shipped proofs.
- [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md) — normative canonical-form spec.
- [`docs/REPRODUCING.md`](../../docs/REPRODUCING.md) — external-rebuild guide.
- [`docs/INTEROP_OVERVIEW.md`](../../docs/INTEROP_OVERVIEW.md) — the full 5-layer interop catalogue.
- [`src/ophamin/measuring/scenarios/immune_siege.py`](../../src/ophamin/measuring/scenarios/immune_siege.py) — the scenario source.
- [Kimera-SWM `EMPIRICAL_VALIDATION.md`](https://github.com/IdirBenSlama/Kimera-SWM-System/blob/KIMERA-SWM/EMPIRICAL_VALIDATION.md) — Kimera-side claim record this proof family contributes to.
