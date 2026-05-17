# RFC NNNN — <one-line title>

| | |
|---|---|
| **Status** | DRAFT |
| **Author** | `<your name + email or GitHub handle>` |
| **Created** | `YYYY-MM-DD` |
| **Last updated** | `YYYY-MM-DD` |
| **Discussion** | `<link to GitHub PR>` |
| **Implementation PR(s)** | `<filled in once ACCEPTED>` |

> Replace `NNNN` with the next available RFC number once the PR is
> ready to merge. Replace `<one-line title>` with a concrete noun
> phrase, e.g. "introduce a TelemetryProbe Protocol" or "deprecate the
> `DriftScan/1` schema in favour of `DriftScan/2`".

---

## 1. Summary

One paragraph — what is this RFC proposing, and why now? A reader
should understand the **what** + **why** from this paragraph alone.

## 2. Problem statement

What concrete problem is this RFC solving? Cite a specific failure
mode, missing capability, or limitation of the current design. If the
problem is "we should be able to X but the framework refuses", paste
the exact error message and the trace. If the problem is "Y is
ambiguous", cite the conflicting interpretations.

Aim for evidence, not aspiration.

## 3. Proposed change

The actual proposal. Be specific. If it adds a public API, sketch the
signatures. If it adds a CLI command, show the invocation. If it
changes a schema, show the before/after JSON.

This is the **load-bearing section** — reviewers will read it most
carefully. Don't be vague; specifics force the reviewer to engage with
the actual decisions.

### 3.1 Public surface impact

- **CLI**: <what changes, including new flags / commands>
- **Codec / wire format**: <are any signed schemas affected?>
- **Protocol interface**: <are SubstrateUnderTest / Pillar /
  Scenario / etc. contracts touched?>
- **Optional dependencies**: <does this add a new `[extra]`?>

### 3.2 Backward compatibility

- Reading older records: does this RFC change which old `schema_version`
  values are still readable?
- Writing: do existing producers continue to work unmodified?
- Deprecation: are any current fields / endpoints scheduled for
  removal?

## 4. Alternatives considered

List ≥ 2 alternatives + why-not. "Do nothing" is a legitimate
alternative; explicitly compare against it.

### 4.1 Alternative A: <name>
Brief description; why this isn't the chosen path.

### 4.2 Alternative B: <name>
Brief description; why this isn't the chosen path.

### 4.3 Do nothing
What happens if we don't accept this RFC? Often the right baseline.

## 5. Drawbacks

Be honest. Every design decision has costs. List them.

## 6. Acceptance criteria

How will we know the RFC is implemented correctly? Bulleted, testable.

- [ ] criterion 1 (e.g. "new CLI command `ophamin foo` exits 0 on
      the happy path and 2 on every documented failure")
- [ ] criterion 2 (e.g. "round-trip property test for new schema field
      passes 1000+ Hypothesis examples")
- [ ] criterion 3 (e.g. "CHANGELOG entry + SCHEMAS.md update land
      with the implementation PR")
- [ ] criterion 4 (e.g. "documentation page in docs/ explains the
      new surface with at least one worked example")

## 7. Migration plan

If this RFC introduces a breaking change, how do existing users move
from before to after? Migration script, shim, deprecation cycle —
whichever fits.

Skip this section if no migration is required.

## 8. Open questions

Things the author isn't sure about. Reviewers should answer these in
PR discussion before the RFC merges as ACCEPTED.

## 9. References

- Related RFCs:
- Related issues / PRs:
- Upstream prior art:
- Relevant standards (e.g. JSON Schema spec, CycloneDX spec):
