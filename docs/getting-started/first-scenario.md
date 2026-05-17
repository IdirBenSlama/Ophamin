# Your first scenario in 5 minutes

This page walks through running an existing Ophamin scenario against
the bundled `MockSubstrate` — no external system required, runs in a
few seconds, produces a signed proof record.

## 1. Confirm the install

```bash
ophamin scenario list
```

You should see 19 scenarios across five tiers. Pick one that doesn't
need a real corpus on disk — `BayesianPhiPosteriorScenario` runs
against a Family-L simulation built into the scenario itself:

```bash
ophamin scenario show bayesian-phi-posterior
```

## 2. Run it

The bundled `MockSubstrate` is the default substrate for the demo
mode; for any scenario that doesn't require an external corpus or a
real Kimera repo, no further wiring is needed. From a Python REPL:

```python
from ophamin.measuring.scenarios import BayesianPhiPosteriorScenario
from ophamin.measuring.proof.codec import dump

scenario = BayesianPhiPosteriorScenario(
    simulate_from_family_l=True,
    sample_sizes=(20, 200),
    draws=1000, tune=500,
    seed=42,
)
proof = scenario.run()
dump(proof, "my_first_proof.json")
print(f"verdict: {proof.verdict.outcome}")
print(f"observed: {proof.verdict.observed_value:.4f}")
print(f"threshold: {proof.claim.threshold.describe()}")
print(f"proof_id: {proof.proof_id}")
```

Output:

```
verdict: VALIDATED
observed: 0.3162
threshold: hdi_contraction_ratio <= 0.40 fraction
proof_id: a3b9f8c2…
```

## 3. Verify the proof

The proof is HMAC-signed with the default sign key. Inspect or
validate it:

```bash
ophamin schema info my_first_proof.json
ophamin schema validate my_first_proof.json
```

To verify the signature, pass the key (the framework's default sign
key is `ophamin-default-sign-key`; in production you'd use your own):

```bash
ophamin schema validate my_first_proof.json --key ophamin-default-sign-key
```

## 4. Read the proof

The proof is a 9-section JSON record. Open it in your editor or:

```bash
python -m json.tool my_first_proof.json | less
```

The nine sections:

1. **Identity** — `proof_id`, `schema_version`, `ophamin_version`,
   `created_at`
2. **Claim** — falsifiable statement + operationalisation + threshold
3. **Pre-registration** — `config_hash`, `data_hash`, analysis plan
   captured BEFORE the run
4. **Data** — substrate name + commit + datasets used
5. **Evidence** — per-pillar statistics with library attribution
6. **Verdict** — `VALIDATED` / `REFUTED` / `INCONCLUSIVE`
7. **Reproduction** — exact command + environment lock
8. **Provenance** — W3C PROV-JSON graph
9. **Signature** — HMAC-SHA256 over the canonical JSON form

See [`SCHEMAS.md`](../reference/schemas.md) for the full layout and
versioning policy.

## Next steps

- [Run a full campaign](../tutorials/run-a-campaign.md) — 6 phases
  end-to-end via `ophamin run-all`
- [Write a new scenario](../tutorials/write-a-scenario.md) — bind your
  own corpus + claim
- [Wrap a third-party pillar](../tutorials/wrap-a-pillar.md) — register
  a custom analysis library
