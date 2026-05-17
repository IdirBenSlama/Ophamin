# Security policy

## Supported versions

Ophamin is currently at **0.4.0**. The framework is open-source under
the **Apache License 2.0** (see [`LICENSE`](https://github.com/IdirBenSlama/Ophamin/blob/main/LICENSE) + [`NOTICE`](https://github.com/IdirBenSlama/Ophamin/blob/main/NOTICE)).
Security patches are committed to `main` and released as patch-level
tags as needed.

| Version | Supported |
|---------|-----------|
| 0.4.x   | ✓ (current) |
| 0.3.x   | ✓ (one minor back; security-only) |
| < 0.3.0 | — (encouraged to upgrade) |

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Instead, use GitHub's *private security advisory* feature:

1. Go to https://github.com/IdirBenSlama/Ophamin/security/advisories/new
2. Fill in the advisory form. Include:
   - The version / commit-hash where you found the issue.
   - A clear description of the vulnerability and its impact.
   - Step-by-step reproduction (or a minimal proof of concept).
   - Any suggested mitigation, if you have one.

You will receive an acknowledgement within 5 business days. We will work
with you to verify the issue, develop a fix, and coordinate disclosure.

If you cannot use the private advisory feature, contact the maintainer
directly through the canonical repository's contact channels.

## What's in scope

- Vulnerabilities in `ophamin` package code that would lead to:
  - Remote code execution under realistic adapter / scenario use.
  - Data exfiltration from a substrate's reported records.
  - Forgery of the HMAC-SHA256 signatures on Empirical Proof Records or
    Audit Records.
  - Bypass of the pre-registration discipline (claim modification after
    the data hash is locked).

## What's out of scope

- Vulnerabilities that require an attacker to already have write access to
  the local filesystem or the venv.
- Dependency vulnerabilities — those are tracked separately via Dependabot
  and `pip-audit`; report upstream rather than to this project.
- The hard-coded paths in `examples/run_*.py` (they're examples; users edit
  them for their environment).
- The `KimeraAdapter` running subprocesses with the user's own
  Kimera-supplied Python interpreter — that is the documented adapter model.

## Disclosure policy

We follow a standard 90-day coordinated disclosure timeline by default. If
a fix is available before that window closes, we will release it as soon as
it is safe to do so. Critical issues that are actively exploited in the
wild may be disclosed sooner; very complex issues may need a longer window.
