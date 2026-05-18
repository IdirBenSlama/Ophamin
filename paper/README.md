# Methods paper draft (RFC 0002 Phase E5)

This directory carries the JOSS-style methods paper for the
Ophamin framework. The paper is intended for submission to one
of:

- [JOSS](https://joss.theoj.org/) (Journal of Open Source Software) — short methodology paper, peer-reviewed via GitHub
- [SoftwareX](https://www.sciencedirect.com/journal/softwarex) — Elsevier, software contributions
- [JMLR Open Source Software track](https://jmlr.org/mloss/) — Journal of Machine Learning Research, OSS track

## Submission readiness status

Drafted up through `v0.26.1`. Per [`docs/ELEVATION_ROADMAP_2026_05_16.md`](../docs/ELEVATION_ROADMAP_2026_05_16.md)
§"E5 submission" — the framework-internal scaffolding is shipped;
the items below remain owner-physical:

| Item | State | Owner action |
|---|---|---|
| Paper draft (`paper.md`, ~1900 words) | ✅ Drafted | Re-read for venue fit |
| BibTeX (`paper.bib`) | ✅ 12+ references | None |
| Falsifiable-claims table (this file) | ✅ 12 rows | None |
| Cross-framework validation proofs | ✅ 7 signed VALIDATED records under `proofs/measurement_machinery/` | None |
| Cross-language wire-format ports | ✅ Rust + JS read + write, CI-pinned | None |
| **ORCID iD** | 🔴 Placeholder `0000-0000-0000-0000` | Get ORCID at <https://orcid.org/register> + update `paper.md` front-matter + `CITATION.cff` |
| **Venue choice** | 🔴 Open (JOSS / SoftwareX / JMLR-OSS) | Pick one; current draft fits JOSS most cleanly |
| **Zenodo DOI** | 🔴 Deposit not yet minted | Follow [`docs/ZENODO_DEPOSIT_WORKFLOW.md`](../docs/ZENODO_DEPOSIT_WORKFLOW.md) |
| **Optional figures / tables** | 🟡 Paper has no figures | JOSS doesn't require; SoftwareX / JMLR-OSS benefit from 1-2 |
| **Submission form** | 🔴 Not yet | After above: <https://joss.theoj.org/papers/new> |

## Files

| File | Contents |
|---|---|
| [`paper.md`](paper.md) | Markdown source, JOSS metadata front-matter |
| [`paper.bib`](paper.bib) | BibTeX references |

## Building the paper

JOSS submission uses the Open Journals docker image which
renders Markdown + BibTeX → PDF + JATS XML. To preview locally:

```bash
docker run --rm \
    --volume $PWD/paper:/data \
    --user $(id -u):$(id -g) \
    --env JOURNAL=joss \
    openjournals/inara
```

This produces `paper.pdf` in the `paper/` directory. The
generated PDF is intentionally not checked into the repository —
the source-of-truth artefacts are `paper.md` and `paper.bib`.

## Submission workflow

JOSS submission is initiated through the
[JOSS submissions form](https://joss.theoj.org/papers/new). The
form requires:

1. Repository URL (this repo)
2. Software version (current release tag)
3. Path to `paper.md` in the repo (`paper/paper.md`)
4. ORCID(s) of all authors

Once submitted, JOSS routes the paper to two volunteer
reviewers who use a public GitHub issue as the review thread.
Typical review window is 4–8 weeks for first response.

## Owner-side action sequence

In dependency order, the four blocking items above resolve like
this:

1. **Get an ORCID iD** (free, ~5 min): <https://orcid.org/register>.
   The form asks for first/last name + email. Once minted, the
   ORCID URL replaces `https://orcid.org/0000-0000-0000-0000` in
   both [`CITATION.cff`](../CITATION.cff) and `paper.md` front-matter.
2. **Pick a venue.** Read the [paper draft](paper.md) end-to-end
   and decide JOSS / SoftwareX / JMLR-OSS. Default = JOSS (fits
   the current length + structure cleanly + reviews via public
   GitHub issue thread).
3. **Mint a Zenodo DOI.** Follow
   [`docs/ZENODO_DEPOSIT_WORKFLOW.md`](../docs/ZENODO_DEPOSIT_WORKFLOW.md)
   — concretely: link Zenodo to the GitHub repo, push a release
   tag, the `.zenodo.json` metadata flows through automatically,
   Zenodo mints a DOI. Add the DOI to `CITATION.cff` and
   `paper.md`'s front-matter (`identifiers:` block + `summary:`
   text).
4. **Submit.** JOSS path: <https://joss.theoj.org/papers/new>.
   Form needs (1) repo URL, (2) software version
   (`v0.26.1` or later release tag), (3) path to `paper.md`,
   (4) ORCID(s). Two volunteer reviewers respond in ~4-8 weeks
   via a public GitHub issue.

## Falsifiable claims the paper itself makes

The paper makes empirical claims about the framework's own
behaviour. Each is reproducible from the repository at the
released version (`v0.26.1` or later):

| Claim | Reproducer |
|---|---|
| Bayesian PyMC ↔ NumPyro mean diff $\le 0.05$ | `ophamin scenario bayesian-phi-posterior-crosscheck` |
| Wilson CI scipy ↔ statsmodels agrees at $\le 10^{-9}$ | `ophamin scenario wilson-ci-crosscheck` |
| Spearman ρ scipy ↔ pingouin exact (zero diff) | `ophamin scenario spearman-crosscheck` |
| Pearson r scipy ↔ numpy ↔ pingouin $\le 10^{-9}$ | `ophamin scenario pearson-crosscheck` |
| Welch t scipy ↔ statsmodels ↔ pingouin $\le 10^{-9}$ | `ophamin scenario welch-t-crosscheck` |
| One-way ANOVA scipy ↔ statsmodels ↔ pingouin $\le 10^{-9}$ | `ophamin scenario anova-crosscheck` |
| Mann-Whitney U scipy ↔ pingouin exact under matched continuity | `ophamin scenario mann-whitney-crosscheck` |
| Every seed-taking scenario satisfies the reproducibility audit | `pytest tests/test_framework_wide_reproducibility.py` |
| Canonical-form byte representation is bit-stable across the five fixtures (simple, unicode, numerical_edge, boundary_cases, deeply_nested) | `pytest tests/test_canonical_form_fixtures.py` |
| Rust write-side: a `CanonicalValue` tree built in Rust canonicalises + signs to bytes Python verifies byte-for-byte | `cd crates/ophamin-proof && cargo test writer_conformance` |
| JS write-side: a value tree built in JS canonicalises + signs to bytes Python verifies byte-for-byte | `cd packages/ophamin-proof-js && npm test -- --test-name-pattern 'JS write-side'` |
| Cross-language fixtures: same canonical bytes produced by Python, Rust, and JS on the same input | `.github/workflows/cross-language.yml` (CI gate) |

A reviewer who can run the test suite can independently verify
every claim the paper makes in less than ten minutes of wall time.
See [`docs/REPRODUCING.md`](../docs/REPRODUCING.md) for the full
external-reviewer workflow.
