# API stability policy (Phase E8)

> **Every public Ophamin symbol carries an explicit stability tier.**
> The contract between Ophamin and downstream consumers is encoded in
> code via decorators in [`src/ophamin/_stability.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/_stability.py),
> pinned at PR time via the regression suite in
> [`tests/test_api_stability_contract.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/tests/test_api_stability_contract.py),
> and auditable from a user codebase via the `ophamin api-stability`
> CLI command. This page is the consumer-facing summary.

## The four tiers

| Tier | What it means | Allowed changes at minor | Allowed changes at major |
|---|---|---|---|
| **Stable** | Semver-backed public API. The default tier for every public symbol. | Add optional parameters with defaults; tighten internal implementation that doesn't change observable behaviour. | Rename, remove, change parameter kinds — but only via a deprecation cycle. |
| **Provisional** | Public but subject to change. Useful for letting consumers exercise an API before its shape is frozen. | Anything except wholesale removal. | Anything, including removal. |
| **Internal** | NOT part of the public API. Consumers MUST NOT import these. | Anything. | Anything. |
| **Deprecated** | Scheduled for removal at `removal_version`. Calling the symbol emits a `DeprecationWarning` exactly once per process. | Stays callable; behaviour preserved until removal. | Removed at the documented `removal_version`. |

Mutually exclusive: a symbol is Stable OR Provisional OR Internal at
any one time. **Deprecated** composes with one of those (typically
a previously-Stable symbol becomes Deprecated; never a Provisional
or Internal one).

## Cross-reference to the schema policy

The Python-API stability contract above is the **runtime** counterpart
of the **wire-format** policy in [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md).
Both follow the same shape:

| | Runtime contract (this doc) | Wire-format contract (SCHEMAS.md) |
|---|---|---|
| Stable surface | `@Stable` symbols | `CampaignRecord/2.0`, `EmpiricalProofRecord/1.0`, etc. |
| Forward-additive at minor | New optional parameter | New optional field |
| Breaking at major | Rename / remove | Remove / rename |
| Deprecation cycle | `@Deprecated(removal_version=...)` | Document in "Deprecated fields" row + 1+ minor of read-compat |
| Reader robustness | Default values for new optional params | `from_dict` defaults absent fields |

## Auditing your own codebase

If you depend on Ophamin, run:

```bash
ophamin api-stability check path/to/your/codebase/
```

Reports every reachable import of an `@Deprecated` or `@Internal`
Ophamin symbol, with line numbers + removal-version metadata for the
deprecated ones. Exit code 0 = clean, 1 = at least one violation
(suitable for CI gates in downstream projects).

To list every annotated public symbol grouped by tier:

```bash
ophamin api-stability list
```

JSON output for tooling:

```bash
ophamin api-stability list --json
ophamin api-stability check path/to/code --json
```

## What the framework guarantees

Per the regression suite at [`tests/test_api_stability_contract.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/tests/test_api_stability_contract.py):

1. **Every load-bearing public symbol carries a stability annotation.**
   The test fails loud at PR time if a public symbol drifts un-tagged.
2. **Stable callables' signatures are pinned.** Adding optional
   parameters at the end with defaults passes; renames, removals,
   kind changes (positional → keyword) fail. When a Stable API
   genuinely extends at minor, regenerate the pin via the
   `OPHAMIN_REGENERATE_API_PINS=1` env var (workflow documented at
   the bottom of the test file).
3. **`StabilityInfo` invariants are enforced at construction time.**
   You can't accidentally tag a Stable symbol with a
   `removal_version` (would only make sense for `Deprecated`).

## When you find a deprecation in your code

A `@Deprecated(removal_version=..., replacement=...)` symbol carries
its own migration breadcrumb:

```text
ophamin.foo.old_function is deprecated; scheduled for removal at
version 1.0.0. Use ophamin.foo.new_function instead.
```

Migrate before `removal_version` lands. If the deprecation needs more
context than the warning message captures, check the CHANGELOG entry
for the release that introduced the `@Deprecated` tag.

## Reference

- Decorator implementation: [`src/ophamin/_stability.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/_stability.py)
- Pinning test suite: [`tests/test_api_stability_contract.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/tests/test_api_stability_contract.py)
- CLI handler: `cmd_api_stability` in [`src/ophamin/cli.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/cli.py)
- RFC: [RFC 0002 §3.2 Phase E8](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/rfc/0002-sota-elevation-stages-5-and-6.md)
