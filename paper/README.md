# Methods paper draft (RFC 0002 Phase E5)

This directory carries the JOSS-style methods paper for the
Ophamin framework. The paper is intended for submission to one
of:

- [JOSS](https://joss.theoj.org/) (Journal of Open Source Software) — short methodology paper, peer-reviewed via GitHub
- [SoftwareX](https://www.sciencedirect.com/journal/softwarex) — Elsevier, software contributions
- [JMLR Open Source Software track](https://jmlr.org/mloss/) — Journal of Machine Learning Research, OSS track

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

## What is still owner-side before submission

The paper draft is in `paper.md` at JOSS length (~1500 words);
acceptance criteria items that remain owner-driven:

- **ORCID iD** for the author — the placeholder
  `0000-0000-0000-0000` in the front-matter needs the real
  ORCID before submission.
- **Choice of venue** — JOSS / SoftwareX / JMLR-OSS each have
  slightly different length and structure conventions. The
  current draft fits JOSS most cleanly.
- **Zenodo DOI** — JOSS recommends archiving the released
  version at Zenodo and citing the DOI in the paper. This is
  RFC 0002 Phase E3, which is owner-side because it requires
  a Zenodo account linked to the GitHub repo.
- **Optional figures / tables** — the current paper has no
  figures. JOSS does not require any; SoftwareX and JMLR-OSS
  benefit from one or two. If the venue choice is something
  other than JOSS, consider adding (1) a five-tier scenario
  diagram and (2) a summary table of cross-framework agreement
  results.

## Falsifiable claims the paper itself makes

The paper makes nine empirical claims about the framework's own
behaviour. Each is reproducible from the repository at the
released version:

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
| Canonical-form byte representation is bit-stable across the three fixtures | `pytest tests/test_canonical_form_fixtures.py` |

A reviewer who can run the test suite can independently verify
every claim the paper makes in less than ten minutes of wall time.
