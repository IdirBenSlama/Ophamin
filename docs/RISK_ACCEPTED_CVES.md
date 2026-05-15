# Risk-accepted CVEs

> **Living document — every entry must justify why suppression is safe.**
> Adding a CVE to `DEFAULT_RISK_ACCEPTED_CVES` in
> [`src/ophamin/auditing/pillars/pip_audit_pillar.py`](../src/ophamin/auditing/pillars/pip_audit_pillar.py)
> requires a matching section here.

This file enumerates dependency CVEs that Ophamin's `pip_audit` pillar is
configured to *suppress* by default. Suppression is appropriate only when
the vulnerability is unfixable upstream AND there is no exploitable path
through Ophamin's runtime usage.

For every entry below, three questions must be answered honestly:

1. **What is the vulnerability?** (one sentence)
2. **Is there a fixed version?** (if yes — bump and remove from list)
3. **Is the attack vector reachable from Ophamin's runtime?** (if yes —
   either remove the dep or document compensating controls)

Reviewed 2026-05-15. Re-review whenever pip-audit surfaces new vulns.

---

## CVE-2025-69872 — `diskcache` unsafe pickle deserialization

- **Affected version**: `diskcache <= 5.6.3` (latest is 5.6.3; no fix released)
- **Pulled in by**: `dvc-data → diskcache` (DVC's content-addressed cache)
- **Attack vector**: an attacker who can write to the cache directory can
  cause arbitrary code execution when Ophamin reads from the cache (pickle
  deserialization).
- **Reachability in Ophamin**:
  - Ophamin uses DVC for lineage storage in
    [`src/ophamin/comparing/provenance/`](../src/ophamin/comparing/provenance/)
  - Cache directory is local to the Ophamin install; written and read by
    the same user that runs Ophamin
  - No cross-user attack surface in single-tenant dev / CI usage
  - **Compensating controls**:
    - Cache directory permissions should be user-only (`0700`) on
      multi-user systems
    - If running on shared CI infrastructure, do not share the cache
      between jobs without verification
- **Fix path**: monitor diskcache project for a patched release; bump and
  remove from list when one ships
- **Last reviewed**: 2026-05-15

## PYSEC-2022-42969 — `py` ReDoS in SVN status parsing

- **Affected version**: `py <= 1.11.0` (latest is 1.11.0; project abandoned
  in 2021; no fix will ship)
- **Pulled in by**: `interrogate → py` (docstring coverage tool)
- **Attack vector**: regex-based denial-of-service via crafted Subversion
  status output, when calling `py.path.svnwc.SvnWCCommandPath._svnstatus`
- **Reachability in Ophamin**:
  - Ophamin does not use Subversion anywhere
  - `py.path.svn*` is never called from Ophamin code
  - `interrogate` (the only Ophamin component that pulls `py`) uses
    `py.io` for terminal output, not `py.path.svn*`
  - **Reachable attack surface: zero**
- **Fix path**: replace `interrogate` with a docstring-coverage tool that
  doesn't depend on `py` (`docstr-coverage`?). Tracked as low-priority
  follow-on
- **Last reviewed**: 2026-05-15

---

## How to add a new entry

1. Add the CVE ID to `DEFAULT_RISK_ACCEPTED_CVES` in
   `pip_audit_pillar.py`
2. Add a `## CVE-ID — short description` section here following the
   same template (affected version / pulled-in-by / attack vector /
   reachability / fix path / last reviewed)
3. Run `ophamin verify` to confirm the suppression is wired correctly
4. Commit both files together (do not split — the suppression is
   meaningless without the documented rationale)

## How to remove an entry

If a fix becomes available:

1. Bump the dependency to a non-vulnerable version
2. Remove the CVE ID from `DEFAULT_RISK_ACCEPTED_CVES`
3. Delete the section here
4. Run `ophamin verify` to confirm the CVE no longer surfaces
