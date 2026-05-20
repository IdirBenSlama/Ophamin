"""Agent: scaffold an Ophamin Scenario subclass from a falsifiable claim.

Sister to adapter_gen, but for the scenarios/ tree. Given a claim
(statement + operationalization + threshold + h0 + h1) plus a name +
family, emits a Python module containing a Scenario subclass scaffold:

- Class-level fields (name / tier / family / goal / explanation /
  method / falsification_consequence / corpus_name / target)
- __init__ with the operator-tunable parameters
- build_claim() returning a full Claim
- score() method explicitly raising NotImplementedError with a
  one-line description of what computation needs to happen

The generated scaffold is OPERATOR-EDITED CODE — not executable as-is.
The operator fills in the score() body with the substrate-specific
math. This is by design: an LLM that auto-implemented the scoring
math would be a falsifiability surface (it could silently match the
threshold). The agent stops at the boundary where statistical
computation begins.

CODER tier (qwen3-coder-next on LM Studio; qwen2.5-coder:32b on Ollama).

Closes the operator loop:

    prereg (claim) → scenario-gen (claim) → operator fills score()
      → run → confounds (validated_proof) → scenario-gen (new claim)
      → ...
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ophamin import __version__
from ophamin.agentic.audit import LLMCallRecord, persist_call
from ophamin.agentic.client import LLMClient, LLMResponse
from ophamin.agentic.models import pick_model


_SYSTEM_PROMPT = """You write Python modules for the Ophamin scenarios layer.
Each module implements a `Scenario` subclass that binds a claim to a
substrate-under-test, runs the corpus through it, scores the run, and
emits a signed `EmpiricalProofRecord`.

The CONTRACT every Scenario subclass must follow:

1. Module docstring: 1-3 paragraphs describing what is tested + the
   falsifiable claim shape + the falsification consequence.
2. Imports: `from ophamin.measuring.scenarios.base import Scenario,
   ScenarioScore, Tier`; the proof types from `ophamin.measuring.proof`
   (`Claim`, `Threshold`); typing as needed.
3. Subclass of `Scenario` with class-level fields:
   - `name`        : kebab-case unique identifier (no spaces)
   - `tier`        : `Tier.SCIENTIFIC` (default) or `Tier.OPERATIONAL`
   - `family`      : short topic family (e.g. "memory", "prime", "immune")
   - `goal`        : one-sentence high-level question
   - `explanation` : 2-4 sentences explaining the test
   - `method`      : statistic name (e.g. "jaccard_floor", "bootstrap_ci")
   - `falsification_consequence` : 1-2 sentences on what REFUTED would mean
   - `corpus_name` : identifier for the corpus this consumes
   - `target`      : substrate-side label
4. `__init__` accepting the operator-tunable params + the input path
   (trajectory / dataset). Validate inputs eagerly (FileNotFoundError,
   ValueError on out-of-range thresholds, etc.) — NO silent fallbacks.
5. `build_claim() -> Claim` returning the full Claim dataclass with all
   five fields (statement, operationalization, threshold, h0, h1).
6. `score(cycle_results, records) -> ScenarioScore`. **STUB ONLY** —
   raise NotImplementedError with a one-line description of what the
   operator needs to implement. The agent must NOT invent the
   statistical computation; that's the operator's responsibility (an
   LLM that auto-implemented score() would be a falsifiability surface).

OUTPUT FORMAT: respond with the raw Python source code only. No prose,
no markdown fences, no explanation. The output should be drop-in
saveable as a .py file under src/ophamin/measuring/scenarios/.
"""


_EXAMPLE_SCENARIO = '''"""The Memory-As-Deformation scenario — cycle-level recognition stability.

Tests whether the substrate's concept-extraction layer recognizes
re-exposed content reliably (Jaccard floor >= 0.80) despite intervening
accumulated experience. Falsification consequence: the substrate's
recognition layer regressed beyond the noise bound — same content
produces substantially different concept sets across re-exposures.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ophamin.measuring.proof import Claim, Threshold
from ophamin.measuring.scenarios.base import Scenario, ScenarioScore, Tier
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult


class MemoryAsDeformationScenario(Scenario):
    """Recognition stable, halt mode CAN flip across re-exposures."""

    name = "memory-as-deformation"
    tier = Tier.SCIENTIFIC
    family = "memory"
    goal = (
        "Test whether the substrate's concept-extraction layer is "
        "substrate-state-INDEPENDENT under re-exposure."
    )
    explanation = (
        "Re-exposure pairs (same stimulus at distinct cycle indices "
        "with intervening experience) should produce concept sets "
        "with Jaccard >= floor. The threshold sits below the "
        "empirically measured floor; REFUTED would mean the "
        "recognition layer regressed."
    )
    method = "jaccard_floor"
    falsification_consequence = (
        "The substrate's concept-recognition layer regressed beyond "
        "the noise bound; same content produces substantially "
        "different concept sets across re-exposures."
    )
    corpus_name = "kimera-trajectory-with-reexposure"
    target = "captured_takwin_trajectory"

    def __init__(
        self,
        trajectory_path: str | Path,
        *,
        concept_jaccard_floor: float = 0.80,
    ) -> None:
        self.trajectory_path = Path(trajectory_path).expanduser()
        if not self.trajectory_path.is_file():
            raise FileNotFoundError(
                f"trajectory_path not found: {self.trajectory_path}"
            )
        if not 0.0 < concept_jaccard_floor <= 1.0:
            raise ValueError(
                f"concept_jaccard_floor must be in (0, 1], got "
                f"{concept_jaccard_floor}"
            )
        self.concept_jaccard_floor = float(concept_jaccard_floor)

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"For re-exposure pairs in a Takwin trajectory, "
                f"concept-set Jaccard floor is >= {self.concept_jaccard_floor:.0%}."
            ),
            operationalization=(
                "Auto-detect re-exposure pairs (same stimulus at "
                "distinct cycle indices). For each pair, compute "
                "Jaccard on `concepts_sample`. Headline = floor (min)."
            ),
            threshold=Threshold(
                metric="concept_jaccard_floor",
                comparator=">=",
                value=self.concept_jaccard_floor,
                units="proportion",
            ),
            h0=(
                f"concept_jaccard_floor < {self.concept_jaccard_floor} "
                f"\\u2014 substrate recognition layer is brittle."
            ),
            h1=(
                f"concept_jaccard_floor >= {self.concept_jaccard_floor} "
                f"\\u2014 substrate recognition layer is stable."
            ),
        )

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        raise NotImplementedError(
            "Operator: implement the per-pair Jaccard computation + "
            "floor aggregation. See sibling scenarios for the "
            "ScenarioScore shape."
        )
'''


@dataclass(frozen=True)
class ScenarioGenResult:
    source: str
    model: str
    runtime: str
    latency_ms: float
    call_record_path: str


def generate(
    *,
    name: str,
    family: str,
    claim: dict[str, Any] | str | Path,
    corpus_name: str = "",
    target: str = "",
    tier: str = "SCIENTIFIC",
    client: LLMClient | None = None,
    audit: bool = True,
    proofs_root: str = "proofs",
) -> ScenarioGenResult:
    """Generate a Scenario subclass scaffold from a claim.

    Parameters
    ----------
    name:
        Kebab-case scenario name (no spaces); also the module file
        basename without .py extension.
    family:
        Short topic family (e.g. "memory", "prime", "immune"). Drives
        the family class-level field; doesn't constrain file location.
    claim:
        A claim dict (statement / operationalization / threshold /
        h0 / h1), a JSON string, or a path to a JSON file (proof.json
        accepted — nested `claim` key is auto-extracted).
    corpus_name:
        Identifier for the corpus the scenario consumes. Falls back
        to `name`-derived label.
    target:
        Substrate-side label (e.g. "captured_takwin_trajectory").
        Falls back to "substrate_under_test".
    tier:
        "SCIENTIFIC" (default) or "OPERATIONAL". Becomes Tier.<TIER>
        in the generated module.

    Returns
    -------
    ScenarioGenResult with the generated source (operator-edited code)
    + audit-record path.

    The generated `score()` method is intentionally a STUB that raises
    NotImplementedError. The operator implements the substrate-specific
    statistical computation themselves — the agent does not. This is
    by design: an LLM that auto-implemented score() would be a
    falsifiability surface (it could silently match the threshold).
    """
    if client is None:
        client = LLMClient()

    # Normalize claim input the same way prereg + confounds do.
    if isinstance(claim, (str, Path)) and Path(str(claim)).is_file():
        loaded = json.loads(Path(str(claim)).read_text())
    elif isinstance(claim, str):
        loaded = json.loads(claim)
    elif isinstance(claim, dict):
        loaded = claim
    else:
        raise TypeError(
            f"unsupported claim input type: {type(claim).__name__}",
        )
    if "claim" in loaded and isinstance(loaded["claim"], dict):
        claim_dict = loaded["claim"]
    else:
        claim_dict = loaded

    if tier.upper() not in ("SCIENTIFIC", "OPERATIONAL"):
        raise ValueError(
            f"tier must be one of SCIENTIFIC / OPERATIONAL, got {tier!r}"
        )

    effective_corpus = corpus_name or f"{name}-corpus"
    effective_target = target or "substrate_under_test"

    user_prompt = (
        f"Scenario name (kebab-case): {name}\n"
        f"Family:                     {family}\n"
        f"Tier:                       Tier.{tier.upper()}\n"
        f"Corpus name:                {effective_corpus}\n"
        f"Target substrate label:     {effective_target}\n\n"
        "Falsifiable claim to bind:\n"
        "```json\n"
        + json.dumps(claim_dict, indent=2, default=str)
        + "\n```\n\n"
        "Generate the Scenario subclass module. Honor the CONTRACT:\n"
        "  - Module docstring derived from the claim's statement +\n"
        "    falsification_consequence.\n"
        "  - All class-level fields populated.\n"
        "  - __init__ validates inputs eagerly; NO silent fallbacks.\n"
        "  - build_claim() returns the claim with the threshold values\n"
        "    drawn from the operator-tunable __init__ params.\n"
        "  - score() raises NotImplementedError with a one-line\n"
        "    operator hint of what to compute. Do NOT invent the\n"
        "    statistical math.\n"
        "Output ONLY the Python source — no markdown fences, no prose."
    )

    mc = pick_model("scenario_gen")
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": "Here is one reference scenario:\n\n"
                                     + _EXAMPLE_SCENARIO},
        {"role": "assistant", "content": (
            "Understood. The pattern: module docstring, imports, "
            "Scenario subclass with all 9 class-level fields, __init__ "
            "with eager validation, build_claim() returning a Claim, "
            "and score() as a NotImplementedError stub. I will emit "
            "only raw Python source."
        )},
        {"role": "user", "content": user_prompt},
    ]

    resp: LLMResponse = client.chat(
        model=mc.model, messages=messages,
        max_tokens=mc.max_tokens, temperature=0.2,
    )

    # Strip a markdown fence if the model added one despite instructions.
    source = resp.content.strip()
    if source.startswith("```"):
        lines = source.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        source = "\n".join(lines)

    call_path = ""
    if audit:
        rec = LLMCallRecord(
            task="scenario_gen", runtime=client.runtime_hint,
            model=mc.model, messages=messages,
            max_tokens=mc.max_tokens, temperature=0.2,
            response_format="text",
            content=resp.content, finish_reason=resp.finish_reason,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            latency_ms=resp.latency_ms,
            ophamin_version=__version__,
        )
        call_path = str(persist_call(rec, proofs_root=proofs_root))

    return ScenarioGenResult(
        source=source,
        model=mc.model,
        runtime=client.runtime_hint,
        latency_ms=resp.latency_ms,
        call_record_path=call_path,
    )
