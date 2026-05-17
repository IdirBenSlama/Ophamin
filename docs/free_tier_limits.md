# GitHub free-tier limits — what we hit and what substitutes we use

This document captures the GitHub features Ophamin would normally use that
are **paywalled on free-tier private repos**, plus the free-tier substitute
we use today. It exists so a future maintainer doesn't re-discover them.

> Snapshot date: 2026-05-15. GitHub's free-tier policy changes over time
> (last major shift around branch-protection gating happened in 2024-25).
> Re-check at https://docs.github.com/en/billing before relying on this.

## What's blocked on free-tier private

| Feature | Path tried | Substitute |
|---|---|---|
| **Repository rulesets** (modern protection API) | `PUT /repos/.../rulesets` → 403 "Upgrade to GitHub Pro" | Local `pre-push` git hook (`.githooks/pre-push`) running pytest |
| **Classic branch protection** | `PUT /repos/.../branches/main/protection` → 403 same | Same local hook + discipline in `CONTRIBUTING.md` |
| **Code Scanning UI** (SARIF in the Security tab) | `audit.yml` uploads SARIF to `codeql-action/upload-sarif` | Upload step has `continue-on-error: true`; SARIF still archived as a workflow artifact (downloadable from the Actions run) |
| **GitHub Advanced Security** | secret scanning, code scanning UI, push protection | None directly — the `audit` pillar's local SARIF + the workflow artifact are the audit trail |
| **Dependabot security alerts UI** | settings → security & analysis | Dependabot version-update PRs DO run (free-tier) — they appear as regular PRs from `dependabot[bot]`. The security-alert dashboard view is gated. |

## What's free on private repos

| Feature | Notes |
|---|---|
| **GitHub Actions minutes** | 2,000 min/month free on private. Our CI matrix (3.12 + 3.13) + audit + lint uses ~3-4 min per push. Plenty of headroom. |
| **Dependabot version updates** | The PR-creating side is free. We configured weekly cadence in [`.github/dependabot.yml`](https://github.com/IdirBenSlama/Ophamin/blob/main/.github/dependabot.yml). |
| **Workflow artifacts** | 500 MB storage / 1 GB transfer / month free. Audit JSON + SARIF artifacts are small (~10 KB each). |
| **Issues / PRs / Discussions** | Free with no limits. |
| **Webhooks** | Free with no limits. |

## What happens when this repo goes public

If/when Ophamin is published under an open license, the following light up
**for free**:

- Repository rulesets (modern branch protection)
- Classic branch protection rules
- Code Scanning UI (SARIF surfaced in the Security tab)
- Public Dependabot security advisories
- Public discussions
- Stargazers / watchers visibility
- Unlimited Actions minutes (vs 2,000/month on private)

At that point, the `audit.yml` workflow's SARIF upload step will start
populating the Security tab automatically (the step is already in place
with `continue-on-error: true`, so nothing needs to be edited).

## Decision log

- **2026-05-15** — chose to stay on free-tier private. Solo maintainer,
  early-stage project. Branch protection deferred. Pre-push hook is the
  free-tier substitute. Re-evaluate when (a) repo goes public, (b) the
  project takes a second contributor, or (c) GitHub adjusts pricing.
