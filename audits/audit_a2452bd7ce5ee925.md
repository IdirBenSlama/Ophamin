# Ophamin Audit Record

**Audit ID:** `a2452bd7ce5ee925d622454af425df71668b4f7d9685fc83286fd1142118c27d`  
**Schema:** vaudit/1.1  
**Captured:** 2026-05-31T16:35:11.982471+00:00  

## 1. Identity

- Ophamin: `0.115.2` @ `c4f5440138c4bc6e7f08c17e6a36d1dfb288e0e8`
- Target: `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin`
- Target content hash: `1c3986ba883b98d9…`

## 2. Pillars run

| pillar | tool | version | status | findings | wall-time |
|---|---|---|---|---|---|
| `ruff` | `ruff` | ruff 0.15.13 | ok | 16 | 0.14s |
| `bandit` | `bandit` | bandit 1.9.4 | ok | 119 | 2.00s |

## 3. Summary

- Total findings: **135**
- Pillars run: 2 (ruff, bandit)

### Severity histogram

- `low`: 107
- `high`: 16
- `medium`: 12

### Findings per pillar

- `bandit`: 119
- `ruff`: 16

### Top 20 hotspot files

- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/measuring/scenarios/ear_discrimination.py`: 12 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/seeing/corpus/connectors.py`: 10 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/cli.py`: 9 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/auditing/pillars/_docker_pillar.py`: 6 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/inspecting/inspector.py`: 6 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/comparing/provenance/lineage.py`: 5 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/measuring/scenarios/interoception_fidelity.py`: 4 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/auditing/audit_record.py`: 3 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/auditing/pillars/coverage_pillar.py`: 3 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/auditing/pillars/pip_audit_pillar.py`: 3 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/inspecting/locator.py`: 3 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/measuring/proof/persistence.py`: 3 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/measuring/scenarios/sonarqube_scan.py`: 3 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/seeing/discovery/kimera_inventory.py`: 3 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/seeing/discovery/watcher.py`: 3 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/seeing/substrate/kimera_adapter.py`: 3 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/agentic/client.py`: 2 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/auditing/base.py`: 2 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/auditing/pillars/bandit_pillar.py`: 2 findings
- `/Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin/auditing/pillars/deptry_pillar.py`: 2 findings

## 4. Reproduction
```
ophamin audit /Volumes/Behemoth/Ophamin FrameWork /ophamin/src/ophamin
```

## 5. Signature
- `cd17097e7ba623b2205b3fff7c955e4d423f6f4bb546bbf68dc7054155450f00`

