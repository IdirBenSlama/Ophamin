"""KimeraAdapter — plug Kimera-SWM into Ophamin as a multi-component substrate.

This is the *only* Kimera-coupled file in the framework. It models Kimera-SWM
as what it is: a multi-component entity, not a single cognitive cycle.

An experiment targets either the **whole entity** (``target="entity"`` — the
integrated Takwin cycle) or a **named component** (``"walker"``, ``"gwf"``,
``"rosetta"``, ``"arachne"``, ``"ouroboros"``, ``"pentecost"``, ``"piovra"``,
``"astrolabe"`` …) — each invoked through its own verified entry point.

Two modes:

* ``mode="subprocess"`` — a fresh interpreter per cycle. Leak-free, slow; the
  precision path.
* ``mode="batch"`` — one interpreter, the component constructed once, the whole
  batch looped in-process. Fast; the *density* path. State accumulates across
  the batch, which for most components is the substrate working as designed
  (memory-as-deformation), not a leak.

Performance is **measured, never assumed**: ``measure_throughput`` runs a
bounded batch and reports real cycles/sec on this vessel. ``probe`` verifies
which targets are actually reachable in the connected repo.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ophamin.comparing.provenance.lineage import capture_git_commit
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


@dataclass(frozen=True)
class _TargetSpec:
    """A Kimera component the adapter can target."""

    module: str
    cls: str
    entry: str
    input_kind: str  # string | self_driven | feature_dict | embedding | structured_point | structured_pending
    note: str


#: the components the adapter can target — verified against the real repo
KIMERA_TARGETS: dict[str, _TargetSpec] = {
    "entity": _TargetSpec(
        "kimera_swm.domain.cognitive.takwin", "Takwin", "run", "string",
        "the integrated 7-step cognitive cycle (Kimera as a whole entity)",
    ),
    "pentecost": _TargetSpec(
        "kimera_swm.domain.linguistic.one_plus_three_plus_one_enforcer",
        "Pentecost", "enforce_one_plus_three_plus_one", "string",
        "the 1+3+1 multi-language perception organ",
    ),
    "ouroboros": _TargetSpec(
        "kimera_swm.domain.mathematical.ouroboros_kernel", "OuroborosKernel",
        "metabolize", "string", "the self-reference metabolic kernel",
    ),
    "rosetta": _TargetSpec(
        "kimera_swm.domain.semantic.rosetta_stele", "RosettaStele", "process",
        "string", "the universal semantic-address translator",
    ),
    "arachne": _TargetSpec(
        "kimera_swm.domain.prime.arachne_protocol", "ArachneProtocol", "assign",
        "string", "the prime nervous-system registry",
    ),
    "walker": _TargetSpec(
        "kimera_swm.domain.cognitive.prime_topology_walker", "PrimeTopologyWalker",
        "traverse", "self_driven", "manifold traversal / contradiction resolution",
    ),
    "gwf": _TargetSpec(
        "kimera_swm.domain.security.gyroscopic_water_fortress.gwf_protocol",
        "GWFProtocol", "screen_input", "feature_dict",
        "the Gyroscopic Water Fortress immune membrane",
    ),
    "piovra": _TargetSpec(
        "kimera_swm.domain.piovra.arm_ganglion", "ArmGanglion", "assess",
        "embedding", "a Piovra sensory-arm ganglion",
    ),
    "astrolabe": _TargetSpec(
        "kimera_swm.domain.geoid.spherical_5d_geometry", "Astrolabe",
        "calculate_geodesic_distance", "structured_point",
        "the 5D spherical-geometry engine",
    ),
    "atlas": _TargetSpec(
        "kimera_swm.domain.geoid.geoid_1_3_1_enforcement", "Atlas",
        "validate_structure", "structured_pending",
        "the geoid 1+3+1 skeleton enforcer (probe-reachable; structured transform pending)",
    ),
    "spde": _TargetSpec(
        "kimera_swm.infrastructure.temporal.spde_engine", "SPDEEngine",
        "simulation_step", "structured_pending",
        "the semantic-pressure diffusion field (probe-reachable; structured transform pending)",
    ),
}


# The runner executes inside the Kimera venv. It dispatches by target, supports
# --probe (introspect every target), single-cycle, and --batch (construct once,
# loop the batch in-process). Stand-in input transforms (feature dicts, pseudo-
# embeddings, pseudo-5D points) are marked as such in the result — they are
# Ophamin's, not Kimera's own extractors.
_RUNNER_SOURCE = r'''
import sys, json, math, time, hashlib, inspect, traceback, collections, re

TARGETS = {
 "entity":    ("kimera_swm.domain.cognitive.takwin","Takwin","run","string"),
 "pentecost": ("kimera_swm.domain.linguistic.one_plus_three_plus_one_enforcer","Pentecost","enforce_one_plus_three_plus_one","string"),
 "ouroboros": ("kimera_swm.domain.mathematical.ouroboros_kernel","OuroborosKernel","metabolize","string"),
 "rosetta":   ("kimera_swm.domain.semantic.rosetta_stele","RosettaStele","process","string"),
 "arachne":   ("kimera_swm.domain.prime.arachne_protocol","ArachneProtocol","assign","string"),
 "walker":    ("kimera_swm.domain.cognitive.prime_topology_walker","PrimeTopologyWalker","traverse","self_driven"),
 "gwf":       ("kimera_swm.domain.security.gyroscopic_water_fortress.gwf_protocol","GWFProtocol","screen_input","feature_dict"),
 "piovra":    ("kimera_swm.domain.piovra.arm_ganglion","ArmGanglion","assess","embedding"),
 "astrolabe": ("kimera_swm.domain.geoid.spherical_5d_geometry","Astrolabe","calculate_geodesic_distance","structured_point"),
 "atlas":     ("kimera_swm.domain.geoid.geoid_1_3_1_enforcement","Atlas","validate_structure","structured_pending"),
 "spde":      ("kimera_swm.infrastructure.temporal.spde_engine","SPDEEngine","simulation_step","structured_pending"),
}

def emit(d):
    sys.stdout.write(json.dumps(d)); sys.stdout.flush()

def jsonable(obj, depth=0):
    if depth > 6:
        return repr(obj)[:200]
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, float):
        return str(obj) if (obj != obj or obj in (float("inf"), float("-inf"))) else obj
    if isinstance(obj, (list, tuple)):
        return [jsonable(x, depth + 1) for x in list(obj)[:400]]
    if isinstance(obj, dict):
        return {str(k): jsonable(v, depth + 1) for k, v in list(obj.items())[:2000]}
    import dataclasses
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        try:
            return {f.name: jsonable(getattr(obj, f.name), depth + 1) for f in dataclasses.fields(obj)}
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return {str(k): jsonable(v, depth + 1) for k, v in vars(obj).items()}
        except Exception:
            pass
    return repr(obj)[:200]

def stable_hash(text):
    return int(hashlib.sha256(str(text).encode("utf-8", "replace")).hexdigest(), 16)

def text_to_features(text):
    # OPHAMIN STAND-IN feature extraction -- NOT Kimera's own extractor.
    t = str(text); n = max(1, len(t))
    counts = collections.Counter(t)
    entropy = -sum((c / n) * math.log2(c / n) for c in counts.values()) if n > 1 else 0.0
    return {
        "length": float(len(t)),
        "word_count": float(len(t.split())),
        "entropy": float(entropy),
        "uppercase_ratio": sum(ch.isupper() for ch in t) / n,
        "digit_ratio": sum(ch.isdigit() for ch in t) / n,
        "special_ratio": sum((not ch.isalnum() and not ch.isspace()) for ch in t) / n,
        "max_char_run": float(max((len(s) for s in re.findall(r"(.)\1*", t)), default=1)),
    }

def text_to_embedding(text, dim=300):
    # OPHAMIN STAND-IN embedding -- NOT Kimera's own encoder.
    import numpy as np
    rng = np.random.default_rng(stable_hash(text) % (2 ** 32))
    v = rng.standard_normal(dim).astype("float32")
    nrm = float(np.linalg.norm(v))
    return v / nrm if nrm > 0 else v

def text_to_5d_point(text):
    import numpy as np
    rng = np.random.default_rng(stable_hash(text) % (2 ** 32))
    v = rng.standard_normal(5)
    return (v / np.linalg.norm(v)).astype("float64")

def construct(target, params):
    mod, cls, entry, kind = TARGETS[target]
    module = __import__(mod, fromlist=[cls])
    C = getattr(module, cls)
    if kind == "structured_pending":
        raise RuntimeError(
            "target '%s' needs a structured-input transform -- reachable via "
            "--probe, not yet wired for run_cycle" % target)
    if target == "piovra":
        return C(arm_id="ophamin_arm", input_dim=300)
    if target == "walker":
        return None  # walker is constructed per-stimulus (graph seed)
    return C()

def invoke(target, stimulus, params, component):
    mod, cls, entry, kind = TARGETS[target]
    text = "" if stimulus is None else str(stimulus)
    extra = {}
    if target == "entity":
        result = component.run(text)
    elif target == "pentecost":
        result = component.enforce_one_plus_three_plus_one(text)
    elif target == "ouroboros":
        result = component.metabolize(text, float(params.get("complexity", 0.5)))
    elif target == "rosetta":
        result = component.process(text)
    elif target == "arachne":
        result = component.assign(text)
    elif target == "walker":
        module = __import__(mod, fromlist=[cls]); C = getattr(module, cls)
        walker = C(graph_seed=stable_hash(text) % (2 ** 31))
        result = walker.traverse(max_steps=int(params.get("max_steps", 50)))
    elif target == "gwf":
        feats = text_to_features(text)
        baseline = {k: 0.5 for k in feats}
        result = component.screen_input(feats, baseline)
        extra["feature_extraction"] = "ophamin_standin"
    elif target == "piovra":
        result = component.assess(text_to_embedding(text))
        extra["embedding_source"] = "ophamin_standin"
    elif target == "astrolabe":
        a = text_to_5d_point(text)
        b = text_to_5d_point("ophamin_reference_point")
        result = component.calculate_geodesic_distance(a, b)
        extra["point_source"] = "ophamin_standin"
    else:
        raise RuntimeError("unknown target %r" % target)
    raw = jsonable(result)
    if not isinstance(raw, dict):
        raw = {"result": raw}
    success, halt_mode = True, None
    for k in ("success", "succeeded", "ok", "is_success"):
        if isinstance(raw.get(k), bool):
            success = raw[k]; break
    for k in ("halt_mode", "halt", "halt_reason", "termination_mode", "verdict", "decision"):
        if raw.get(k) is not None:
            halt_mode = str(raw[k]); break
    raw.update(extra)
    return raw, success, halt_mode

def probe():
    report = {}
    for name, (mod, cls, entry, kind) in TARGETS.items():
        e = {"module": mod, "class": cls, "entry": entry, "input_kind": kind}
        try:
            module = __import__(mod, fromlist=[cls]); C = getattr(module, cls)
            e["import_ok"] = True
            try:
                e["init_sig"] = str(inspect.signature(C.__init__))
            except Exception:
                e["init_sig"] = "<unavailable>"
        except Exception as ex:
            e["import_ok"] = False
            e["error"] = ("%s: %s" % (type(ex).__name__, ex))[:240]
        report[name] = e
    return report

def main():
    if len(sys.argv) < 2:
        emit({"ok": False, "error": "repo path argument missing"}); return
    repo = sys.argv[1]; sys.path.insert(0, repo)
    flags = sys.argv[2:]
    if "--probe" in flags:
        try:
            emit({"ok": True, "probe": probe()})
        except Exception as e:
            emit({"ok": False, "stage": "probe", "error": str(e),
                  "traceback": traceback.format_exc()})
        return
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception as e:
        emit({"ok": False, "stage": "payload", "error": str(e)}); return
    target = payload.get("target", "entity")
    params = payload.get("params") or {}
    if target not in TARGETS:
        emit({"ok": False, "stage": "target", "error": "unknown target %r" % target}); return
    if "--batch" in flags:
        stimuli = payload.get("stimuli") or []
        results_path = payload.get("results_path")  # incremental-emit sink
        t_construct = time.perf_counter()
        try:
            component = construct(target, params)
        except Exception as e:
            emit({"ok": False, "stage": "construct", "error": str(e),
                  "traceback": traceback.format_exc()}); return
        construct_seconds = time.perf_counter() - t_construct
        # Stream every cycle to a JSONL sink as it completes. A kill / timeout
        # then still leaves the finished cycles on disk -- the adapter reads
        # them back instead of losing the whole batch. Line-buffered + an
        # explicit flush per cycle so a SIGKILL cannot lose a completed line.
        sink = open(results_path, "w", buffering=1) if results_path else None
        results = []
        for i, s in enumerate(stimuli):
            t_cycle = time.perf_counter()
            try:
                raw, success, halt = invoke(target, s, params, component)
                entry = {"cycle_index": i, "ok": True, "raw": raw,
                         "success": success, "halt_mode": halt,
                         "cycle_seconds": time.perf_counter() - t_cycle}
            except Exception as e:
                entry = {"cycle_index": i, "ok": False,
                         "cycle_seconds": time.perf_counter() - t_cycle,
                         "error": str(e),
                         "traceback": traceback.format_exc()[-1500:]}
            results.append(entry)
            if sink is not None:
                sink.write(json.dumps(entry) + "\n"); sink.flush()
        if sink is not None:
            sink.close()
        emit({"ok": True, "batch": results, "construct_seconds": construct_seconds})
        return
    stimulus = payload.get("stimulus")
    try:
        component = construct(target, params)
        raw, success, halt = invoke(target, stimulus, params, component)
        emit({"ok": True, "raw": raw, "success": success, "halt_mode": halt})
    except Exception as e:
        emit({"ok": False, "stage": "run", "error": str(e),
              "traceback": traceback.format_exc()})

if __name__ == "__main__":
    main()
'''


class KimeraAdapterError(RuntimeError):
    """Raised when the adapter itself is misconfigured (not a cycle failure)."""


class KimeraAdapter(SubstrateUnderTest):
    """Subprocess adapter for the Kimera-SWM substrate — entity or any component."""

    name = "kimera-swm"

    def __init__(
        self,
        kimera_repo: str | Path,
        python_exe: str | Path | None = None,
        target: str = "entity",
        mode: str = "subprocess",
        runner_script: str | Path | None = None,
        timeout: float = 300.0,
        batch_timeout: float = 3600.0,
        env: dict[str, str] | None = None,
    ) -> None:
        if target not in KIMERA_TARGETS:
            raise KimeraAdapterError(
                f"unknown target {target!r}; choose from {sorted(KIMERA_TARGETS)}"
            )
        if mode not in ("subprocess", "batch"):
            raise KimeraAdapterError("mode must be 'subprocess' or 'batch'")

        self.kimera_repo = Path(kimera_repo).expanduser()
        if not self.kimera_repo.exists():
            raise KimeraAdapterError(f"Kimera repo not found: {self.kimera_repo}")
        if not (self.kimera_repo / "kimera_swm").exists():
            raise KimeraAdapterError(
                f"{self.kimera_repo} does not look like a Kimera repo (no kimera_swm/)"
            )

        if python_exe is not None:
            self.python_exe = Path(python_exe).expanduser()
        else:
            self.python_exe = self.kimera_repo / ".venv" / "bin" / "python"
        if not self.python_exe.exists():
            raise KimeraAdapterError(
                f"python interpreter not found: {self.python_exe} — pass python_exe"
            )

        self.target = target
        self.mode = mode
        self.timeout = float(timeout)
        self.batch_timeout = float(batch_timeout)
        # extra environment for the Kimera subprocess (e.g. the GPU-acceleration
        # flag) — merged over os.environ, never replacing it
        self.env = dict(env) if env else {}
        self._owns_runner = runner_script is None
        if runner_script is not None:
            self.runner_script = Path(runner_script).expanduser()
            if not self.runner_script.exists():
                raise KimeraAdapterError(f"runner script not found: {self.runner_script}")
        else:
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix="_ophamin_kimera_runner.py", delete=False
            )
            tmp.write(_RUNNER_SOURCE)
            tmp.close()
            self.runner_script = Path(tmp.name)

    # -- subprocess plumbing ------------------------------------------------

    @staticmethod
    def write_runner_template(path: str | Path) -> Path:
        """Dump the bundled runner so it can be edited and reused."""
        path = Path(path)
        path.write_text(_RUNNER_SOURCE, encoding="utf-8")
        return path

    def git_commit(self) -> str:
        return capture_git_commit(self.kimera_repo)

    def reset(self) -> None:
        # subprocess mode: every cycle is a fresh interpreter, nothing to reset.
        # batch mode: each run_batch builds its own process. Documented no-op.
        return None

    def _invoke(
        self,
        payload: dict[str, Any] | None,
        *,
        probe: bool = False,
        batch: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        cmd = [str(self.python_exe), str(self.runner_script), str(self.kimera_repo)]
        if probe:
            cmd.append("--probe")
        if batch:
            cmd.append("--batch")
        try:
            completed = subprocess.run(
                cmd,
                input=json.dumps(payload or {}),
                capture_output=True,
                text=True,
                timeout=timeout if timeout is not None else self.timeout,
                cwd=str(self.kimera_repo),  # Kimera's caches land in its own tree
                env={**os.environ, **self.env},  # e.g. the GPU-acceleration flag
            )
        except subprocess.TimeoutExpired as exc:
            return {"ok": False, "stage": "timeout", "error": str(exc)}
        if not completed.stdout.strip():
            return {
                "ok": False,
                "stage": "subprocess",
                "error": f"runner produced no output (exit {completed.returncode})",
                "traceback": completed.stderr[-4000:],
            }
        try:
            return json.loads(completed.stdout.strip().splitlines()[-1])
        except json.JSONDecodeError as exc:
            return {
                "ok": False,
                "stage": "decode",
                "error": f"runner output was not JSON: {exc}",
                "traceback": completed.stdout[-2000:] + "\n--- stderr ---\n"
                + completed.stderr[-2000:],
            }

    # -- the SubstrateUnderTest contract ------------------------------------

    def _to_cycle_result(
        self, result: dict[str, Any], stimulus: Any, cycle_index: int
    ) -> CycleResult:
        if not result.get("ok"):
            return CycleResult(
                cycle_index=cycle_index,
                success=False,
                raw={"stage": result.get("stage"), "traceback": result.get("traceback")},
                halt_mode="adapter_error",
                stimulus_id=str(stimulus) if stimulus is not None else None,
                error=str(result.get("error", "unknown adapter error")),
            )
        raw = result.get("raw")
        raw = raw if isinstance(raw, dict) else {"result": raw}
        return CycleResult(
            cycle_index=cycle_index,
            success=bool(result.get("success", True)),
            raw=raw,
            halt_mode=result.get("halt_mode"),
            stimulus_id=str(stimulus) if stimulus is not None else None,
        )

    def run_cycle(
        self, stimulus: Any, params: dict[str, Any] | None = None
    ) -> CycleResult:
        payload = {"target": self.target, "stimulus": stimulus, "params": params or {}}
        result = self._invoke(payload)
        return self._to_cycle_result(result, stimulus, 0)

    def run_batch(
        self, stimuli: list[Any], params: dict[str, Any] | None = None
    ) -> list[CycleResult]:
        if self.mode != "batch":
            # subprocess mode: honour the precision path — one interpreter per cycle
            return super().run_batch(stimuli, params)
        # incremental-emit: the runner streams each cycle to a JSONL sink as it
        # completes, so a timeout or crash still yields the cycles that finished
        # — the adapter reads them back rather than discarding the whole batch.
        sink = tempfile.NamedTemporaryFile(
            mode="w", suffix="_ophamin_batch_results.jsonl", delete=False
        )
        sink.close()
        results_path = sink.name
        payload = {
            "target": self.target,
            "stimuli": list(stimuli),
            "params": params or {},
            "results_path": results_path,
        }
        try:
            result = self._invoke(payload, batch=True, timeout=self.batch_timeout)
            # happy path: the runner returned a clean batch on stdout — authoritative
            if result.get("ok") and "batch" in result:
                out: list[CycleResult] = []
                for entry in result.get("batch", []):
                    idx = int(entry.get("cycle_index", len(out)))
                    stimulus = stimuli[idx] if idx < len(stimuli) else None
                    out.append(self._to_cycle_result(entry, stimulus, idx))
                return out
            # timeout / crash: reconstruct from the incremental sink — the cycles
            # that completed are real measurements; the unreached tail becomes an
            # adapter_error, so a 7000/7270 timeout is real data, not all-or-nothing
            completed: dict[int, dict[str, Any]] = {}
            try:
                with open(results_path) as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue  # a half-written final line after a hard kill
                        if "cycle_index" in entry:
                            completed[int(entry["cycle_index"])] = entry
            except OSError:
                pass
            return [
                self._to_cycle_result(completed.get(i, result), s, i)
                for i, s in enumerate(stimuli)
            ]
        finally:
            try:
                Path(results_path).unlink(missing_ok=True)
            except OSError:
                pass

    # -- adapter-specific capabilities --------------------------------------

    def probe(self) -> dict[str, Any]:
        """Verify which targets are reachable in the connected repo.

        Returns a structured report — run this before wiring scenarios. It is
        how the adapter checks the substrate, not the docs.
        """
        report: dict[str, Any] = {
            "kimera_repo": str(self.kimera_repo),
            "python_exe": str(self.python_exe),
            "git_commit": self.git_commit(),
        }
        result = self._invoke(None, probe=True)
        report["runner_ok"] = bool(result.get("ok"))
        if result.get("ok"):
            report["targets"] = result.get("probe", {})
        else:
            report["error"] = result.get("error")
            report["traceback"] = result.get("traceback")
        return report

    def measure_throughput(
        self, stimuli: list[Any], params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Measure real cycles/sec for this target — performance is measured, not assumed.

        Runs the stimuli as one in-process batch and times it. The result is the
        empirical basis for choosing subprocess-vs-batch and for a throughput
        proof record — there is no assumed performance figure anywhere.
        """
        if not stimuli:
            raise ValueError("measure_throughput needs at least one stimulus")
        payload = {"target": self.target, "stimuli": list(stimuli), "params": params or {}}
        start = time.perf_counter()
        result = self._invoke(payload, batch=True, timeout=self.batch_timeout)
        wall = time.perf_counter() - start
        n = len(stimuli)
        if not result.get("ok"):
            return {
                "target": self.target,
                "n": n,
                "wall_seconds": wall,
                "cycles_per_sec": 0.0,
                "ok": False,
                "error": result.get("error"),
            }
        batch = result.get("batch", [])
        succeeded = sum(1 for e in batch if e.get("ok") and e.get("success", True))
        construct_seconds = float(result.get("construct_seconds", 0.0))
        cycle_times = [float(e["cycle_seconds"]) for e in batch if "cycle_seconds" in e]
        median_cycle = statistics.median(cycle_times) if cycle_times else 0.0
        mean_cycle = statistics.fmean(cycle_times) if cycle_times else 0.0
        return {
            "target": self.target,
            "mode": "batch",
            "n": n,
            "completed": len(batch),
            "succeeded": succeeded,
            "wall_seconds": wall,
            # one-time Kimera component construction (separated from per-cycle cost)
            "construct_seconds": construct_seconds,
            # gross rate — includes subprocess spawn + import + construction
            "gross_cycles_per_sec": n / wall if wall > 0 else 0.0,
            # steady-state rate — construction excluded, the true per-cycle figure
            "median_cycle_seconds": median_cycle,
            "mean_cycle_seconds": mean_cycle,
            "steady_state_cycles_per_sec": (1.0 / median_cycle) if median_cycle > 0 else 0.0,
            "env": dict(self.env),
            "ok": True,
        }

    def metadata(self) -> dict[str, Any]:
        spec = KIMERA_TARGETS[self.target]
        return {
            "name": self.name,
            "git_commit": self.git_commit(),
            "kind": "kimera",
            "target": self.target,
            "target_class": f"{spec.module}.{spec.cls}",
            "target_entry": spec.entry,
            "target_input_kind": spec.input_kind,
            "mode": self.mode,
            "kimera_repo": str(self.kimera_repo),
            "python_exe": str(self.python_exe),
        }

    def __del__(self) -> None:  # best-effort cleanup of the temp runner
        try:
            if getattr(self, "_owns_runner", False):
                Path(self.runner_script).unlink(missing_ok=True)
        except Exception:
            pass
