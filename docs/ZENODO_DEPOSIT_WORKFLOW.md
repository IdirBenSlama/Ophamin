# Zenodo deposit workflow (RFC 0002 Phase E3 closeout)

> **Audience:** the owner. This page walks through the concrete
> action sequence to mint a Zenodo DOI for Ophamin. It is the
> owner-physical half of RFC 0002 Phase E3 — the framework-internal
> metadata (`.zenodo.json`, `CITATION.cff`) is already shipped; the
> Zenodo account + release-tag-push are not auto-doable.

A Zenodo DOI unlocks two things:

1. **Citability** — every release of Ophamin gets a permanent DOI
   citable in academic papers, even after Ophamin's GitHub repo
   moves or is renamed.
2. **JOSS prerequisite** — JOSS submissions are reviewed against a
   Zenodo-archived release; the DOI is a required field on the
   submission form.

Total wall time: **~10 minutes**, mostly clicking through Zenodo's
UI once. Subsequent releases are automatic — every GitHub release
mints a new DOI without further action.

---

## What's already shipped (no action needed)

- [`.zenodo.json`](https://github.com/IdirBenSlama/Ophamin/blob/main/.zenodo.json)
  at the repo root. Zenodo reads this on each release to populate
  the deposit's metadata: title, description, license, keywords,
  related identifiers (SCHEMAS.md + paper/paper.md).
- [`CITATION.cff`](https://github.com/IdirBenSlama/Ophamin/blob/main/CITATION.cff)
  at the repo root. GitHub renders a "Cite this repository" button
  using this; Zenodo also reads it for additional metadata.

The framework-internal scaffolding lands updates to both files in
every relevant release (most recently `0.22.0` for the interop-arc
refresh + `0.26.1` for the current-version bump).

---

## Step 1 — Get an ORCID iD (one-time, ~5 min)

ORCID is a free researcher identifier required by JOSS / SoftwareX
/ JMLR-OSS. Register at <https://orcid.org/register>.

The form asks for first name, last name, and email. After
registration you'll get a 16-digit ID in the form
`https://orcid.org/0000-XXXX-YYYY-ZZZZ`.

**After ORCID is minted**, update three files:

1. `CITATION.cff` line 10: replace the `orcid:` value.
2. `paper/paper.md` line 12: replace the `orcid:` front-matter
   value.
3. `.zenodo.json` — add to the creator block:
   ```json
   "creators": [
     {
       "name": "Ben Slama, Idir",
       "affiliation": "Independent",
       "orcid": "0000-XXXX-YYYY-ZZZZ"
     }
   ]
   ```

This step is owner-physical because ORCID is bound to a real
researcher identity.

---

## Step 2 — Link Zenodo to the GitHub repo (one-time, ~3 min)

1. Sign in at <https://zenodo.org/login/> using GitHub OAuth. (If
   you don't have a Zenodo account yet, this creates one.)
2. Authorize the Zenodo GitHub app when prompted — it needs
   permission to read repo metadata + react to release events.
3. Navigate to <https://zenodo.org/account/settings/github/>. You
   should see a list of every repo you have admin on.
4. Find `IdirBenSlama/Ophamin` in the list and **flip the toggle
   to ON**. This subscribes Zenodo to release events for the repo.

Once toggled on, Zenodo watches for new GitHub releases and
automatically creates a deposit + mints a DOI for each one.

This step is owner-physical because it requires real Zenodo +
GitHub account authentication.

---

## Step 3 — Push a release tag (~30 seconds)

Zenodo only mints DOIs from **GitHub releases** (the formal
release object), not bare git tags. The release object can be
created via the GitHub UI or the `gh` CLI:

```bash
# Tag the current main + create a GitHub release
gh release create v0.26.1 \
    --title "Ophamin v0.26.1" \
    --notes "See CHANGELOG.md for details."
```

Within ~60 seconds of the release event, Zenodo creates a new
deposit:

- Title, description, keywords, license, related_identifiers all
  flow through from `.zenodo.json`.
- Author block flows through from the creator field
  (`Ben Slama, Idir`, affiliation `Independent`; ORCID populated
  after Step 1).
- A DOI like `10.5281/zenodo.XXXXXXX` is minted.

The DOI is visible at <https://zenodo.org/account/settings/github/>
under the Ophamin repo row, or via the upload page directly.

---

## Step 4 — Record the DOI in the repo (~2 min)

Once the DOI is minted, add it back to the repo so subsequent
citations resolve correctly:

1. `CITATION.cff` — add a `doi:` field at the top level:
   ```yaml
   doi: 10.5281/zenodo.XXXXXXX
   ```
2. `paper/paper.md` — add a `bibliography:` reference and cite the
   DOI in the `# Summary` section once.
3. `README.md` — add a Zenodo DOI badge near the top:
   ```markdown
   [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXXX)
   ```

Ship these as a patch release (e.g. `0.26.2` "Record Zenodo DOI").

---

## What happens on every subsequent release

Once Step 2 is done, the deposit machinery is fully automatic:

- Every `gh release create` mints a new DOI for that release.
- The **concept DOI** — `10.5281/zenodo.XXXXXXX` with the lowest
  zenodo ID — always points at the *latest* version. Cite this
  one in papers when you want "the latest Ophamin".
- The **version DOIs** — `10.5281/zenodo.YYYYYYY`,
  `10.5281/zenodo.ZZZZZZZ`, etc — each point at a specific
  release. Cite these when you want pinned reproducibility.

The `.zenodo.json` content carries forward unchanged unless you
edit it. Future framework releases that mention Zenodo only need
to bump versions in `CITATION.cff` (already auto-done by every
release in this repo).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No deposit appears after release | Zenodo GitHub toggle not on, or release was created as a tag (not a release) | Re-check Step 2; `gh release list` should show the release |
| DOI minted but no description | `.zenodo.json` not in repo root | Should be present at `/.zenodo.json`; check with `ls .zenodo.json` |
| ORCID rejected by Zenodo | Wrong format (must be `0000-XXXX-YYYY-ZZZZ` 16-digit) | Copy from the canonical ORCID profile URL |
| Description has Markdown that renders raw | Zenodo treats description as plain text | Keep markdown minimal in `.zenodo.json` `description` field |

---

## See also

- [`paper/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/paper/README.md) — paper submission workflow (depends on a Zenodo DOI per Step 3 above).
- [`docs/REPRODUCING.md`](REPRODUCING.md) — external-reviewer rebuild guide; will cite the DOI once minted.
- [`CITATION.cff`](https://github.com/IdirBenSlama/Ophamin/blob/main/CITATION.cff) + [`.zenodo.json`](https://github.com/IdirBenSlama/Ophamin/blob/main/.zenodo.json) — the shipped metadata.
- Zenodo's own docs on GitHub integration: <https://zenodo.org/help/github>.
- ORCID registration: <https://orcid.org/register>.
