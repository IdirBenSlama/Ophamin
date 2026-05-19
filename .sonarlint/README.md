# SonarQube for IDE (formerly SonarLint) — connected-mode binding

> Real-time SonarQube analysis in your editor while you write code,
> using the SAME rules as the CI pipeline + the bundled SonarQube
> instance (`sonar/docker-compose.yml`).

## What this directory does

`.sonarlint/connectedMode.json` binds Ophamin's repo to the local
SonarQube instance at `http://localhost:9000` with project key
`ophamin`. When you open this directory in any SonarLint-compatible
IDE, the extension auto-detects the file + confirms the binding.

## Why "connected mode" (vs standalone)

| Mode | What it gives | What's missing |
|---|---|---|
| **Standalone** (default after install) | Built-in rule set; works offline; instant feedback | No project-specific suppressions; no quality-gate awareness; rules can drift from server |
| **Connected** (this binding) | **Identical rules to server** (same Python analyzer; same custom rules); **quality-gate status visible** in editor; **issues marked "Won't Fix" on the server hide in IDE**; new-code definition matches server | Requires SonarQube reachable |

Connected mode is the canonical way to keep "what fails CI" and
"what shows up in my editor" identical — no more "passes locally,
fails in PR" surprises driven by rule-set drift.

## Quick start

**1. Bring up SonarQube** (if not already running):

```bash
bash scripts/sonar_up.sh
```

**2. Install the SonarQube for IDE extension** for your editor:

| IDE | Extension marketplace link |
|---|---|
| VS Code / VSCodium / Cursor | `SonarSource.sonarlint-vscode` |
| IntelliJ IDEA / PyCharm / WebStorm | `org.sonarlint.idea` |
| Eclipse | SonarLint plugin |
| Visual Studio | SonarSource.SonarQubeForVS |

**3. Open the Ophamin repo** in your IDE. The extension detects
`.sonarlint/connectedMode.json` + offers to bind to the local
instance. Confirm.

**4. (One-time)** Generate a token in the SonarQube web UI at
`http://localhost:9000/account/security` → paste into the IDE
when prompted.

After this, every file you edit gets real-time analysis with the
same rules CI uses. Issues already marked "Won't Fix" on the
server hide automatically; new-code-only quality-gate thresholds
apply to your in-editor changes.

## Why this matters for AI-assisted coding

The directive that drove the original SonarQube ship at 0.50.0 mentioned
generating code "rapidly using agentic tools like Cursor AI or VS
Code". Connected-mode SonarLint is the immediate guardrail:

- **AI-generated code gets analyzed as it lands in your editor** —
  before commit, before PR, before CI runs anything.
- **Bugs + vulnerabilities + code smells surface in real time** —
  no waiting for the CI scan minutes later.
- **Cross-machine consistency** — the rule set comes from the
  shared SonarQube; doesn't drift between developers based on
  installed plugin version.

This closes the **local-guardrails phase** (#3 of 4) of the
SonarQube integration roadmap. CI automation shipped at 0.51.0;
security scanning shipped at 0.52.0; deployment GitOps ships at
0.54.0 (next).

## Overriding for SonarCloud or remote SonarQube

To bind to a remote SonarQube (e.g. an internal company instance
or SonarCloud), the IDE extension's connection settings take
precedence over this file. The bundled binding is the default
for operators using the in-tree `sonar/docker-compose.yml` stack.

## See also

- [SonarQube for IDE documentation](https://docs.sonarsource.com/sonarqube-for-ide/)
- [Connected Mode setup guide (VS Code)](https://docs.sonarsource.com/sonarqube-for-ide/vs-code/team-features/connected-mode/)
- [`docs/SONARQUBE.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/SONARQUBE.md) — full SonarQube integration story
- [`sonar/docker-compose.yml`](https://github.com/IdirBenSlama/Ophamin/blob/main/sonar/docker-compose.yml) — the bundled local instance this binding targets
