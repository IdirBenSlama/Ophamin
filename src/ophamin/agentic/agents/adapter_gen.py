"""Agent: generate a Foreign_Corpus adapter module from a NL description.

Given a one-sentence description + optional source URL / HF id, emits
a Python module matching the existing pattern at
``experiments/foreign_corpus_adapters/`` (load / samples /
feature_summary contract).

The agent does NOT execute the generated code or validate it lands
in the right directory — the operator reviews + saves. Output is
the raw module source; caller decides where to write it.

CODER-tier model by default (qwen2.5-coder:32b for code quality).

Pattern enforced by few-shot prompting with two existing adapters
(esc50_audio + gutenberg_classics) so the generated module respects:

- file-level docstring describing the dataset
- `ROOT = Path("/Volumes/Kaido/Foreign_Corpus/...")`
- `load() -> list[dict]` enumerating metadata
- `samples(meta, ..., n=10) -> list[tuple[str, ...]]`
- `feature_summary(meta) -> str`
- `if __name__ == "__main__":` smoke block
"""

from __future__ import annotations

from dataclasses import dataclass

from ophamin import __version__
from ophamin.agentic.audit import LLMCallRecord, persist_call
from ophamin.agentic.client import LLMClient, LLMResponse
from ophamin.agentic.models import pick_model


_SYSTEM_PROMPT = """You write Python modules for the Ophamin "Foreign Corpus"
adapter layer. Each module loads a specific dataset from disk and exposes a
unified interface so the rest of the framework can consume it.

The CONTRACT every adapter must follow:

1. File docstring: 1-3 paragraphs describing the dataset (size, format, source,
   intended use for Kimera-SWM substrate testing).
2. Module-level `ROOT = Path("/Volumes/Kaido/Foreign_Corpus/<category>/<name>")`.
3. `def load() -> list[dict]` — return metadata records per item.
4. `def samples(meta: list[dict], n: int = 10) -> list[tuple[str, Path]]` —
   yield labelled-path tuples (or `list[tuple[str, dict]]` for non-file data).
5. `def feature_summary(meta: list[dict]) -> str` — one-line description.
6. `if __name__ == "__main__":` smoke block that calls all three.

OUTPUT FORMAT: respond with the raw Python source code only. No prose, no
markdown fences, no explanation. The output should be drop-in saveable as a
.py file.
"""


_EXAMPLE_ESC50 = '''"""Adapter: ESC-50 environmental sound dataset.

50 categories x 40 audio clips each = 2000 5-second WAV files at 44.1 kHz.
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path("/Volumes/Kaido/Foreign_Corpus/sensory_audio/ESC-50-master")


def load() -> list[dict]:
    """Load metadata for all 2000 clips."""
    meta_path = ROOT / "meta" / "esc50.csv"
    with meta_path.open() as f:
        reader = csv.DictReader(f)
        return list(reader)


def samples(meta: list[dict], category: str | None = None,
            n: int = 10) -> list[tuple[str, Path]]:
    items = meta
    if category is not None:
        items = [m for m in meta if m.get("category") == category]
    audio_dir = ROOT / "audio"
    return [(f"esc50_{m['filename'][:-4]}_{m['category']}",
             audio_dir / m["filename"]) for m in items[:n]]


def feature_summary(meta: list[dict]) -> str:
    cats = sorted(set(m["category"] for m in meta))
    return f"ESC-50: {len(meta)} clips x 5s @ 44.1 kHz, {len(cats)} categories"


if __name__ == "__main__":
    m = load()
    print(feature_summary(m))
    for label, p in samples(m, "rain", 3):
        print(f"  {label}: {p.name} ({'OK' if p.exists() else 'MISSING'})")
'''


@dataclass(frozen=True)
class AdapterGenResult:
    """Output of :func:`generate`."""

    source: str                   # the generated Python module source
    model: str                    # which model produced it
    runtime: str                  # ollama / mlx-lm
    latency_ms: float
    call_record_path: str         # absolute path to the audit record (or "" if audit=False)


def generate(
    *,
    name: str,
    description: str,
    category: str = "symbolic",
    on_disk_path: str = "",
    client: LLMClient | None = None,
    audit: bool = True,
    proofs_root: str = "proofs",
) -> AdapterGenResult:
    """Generate an adapter module source from a NL description.

    Parameters
    ----------
    name:
        Module name without extension, kebab- or snake-case
        (e.g. ``"my_new_dataset"``).
    description:
        One-paragraph description of the dataset: size, format,
        source, intended Kimera-side use.
    category:
        Which Foreign_Corpus category directory the dataset lives
        under (``"sensory_audio"`` / ``"biological"`` / etc.).
    on_disk_path:
        Optional explicit path under ``/Volumes/Kaido/Foreign_Corpus/``
        if the dataset doesn't follow ``<category>/<name>``.
    client:
        Optional pre-built :class:`LLMClient`. New default-config
        instance when None.
    audit:
        Persist a signed :class:`LLMCallRecord` under
        ``<proofs_root>/llm_calls/``. Default True.

    Returns
    -------
    AdapterGenResult
        Carries the generated source + audit-record path.
    """
    if client is None:
        client = LLMClient()
    mc = pick_model("adapter_gen")

    user_prompt = (
        f"Dataset name: {name}\n"
        f"Category: {category}\n"
        f"On-disk path: {on_disk_path or f'/Volumes/Kaido/Foreign_Corpus/{category}/{name}'}\n\n"
        f"Description:\n{description}\n\n"
        f"Generate a Python adapter module following the CONTRACT. "
        f"Output ONLY the Python source — no markdown fences, no prose."
    )

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": "Here is one example adapter for reference:\n\n"
                                     + _EXAMPLE_ESC50},
        {"role": "assistant", "content": "Understood. The pattern is: docstring, "
                                          "ROOT constant, load(), samples(), "
                                          "feature_summary(), and a __main__ block. "
                                          "I will emit only raw Python source."},
        {"role": "user", "content": user_prompt},
    ]

    resp: LLMResponse = client.chat(
        model=mc.model,
        messages=messages,
        max_tokens=mc.max_tokens,
        temperature=0.2,
    )

    # Strip a markdown fence if the model added one despite instructions
    source = resp.content.strip()
    if source.startswith("```"):
        # Drop the first ``` line + the trailing ``` line
        lines = source.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        source = "\n".join(lines)

    call_path = ""
    if audit:
        rec = LLMCallRecord(
            task="adapter_gen",
            runtime=client.runtime_hint,
            model=mc.model,
            messages=messages,
            max_tokens=mc.max_tokens,
            temperature=0.2,
            response_format="text",
            content=resp.content,
            finish_reason=resp.finish_reason,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            latency_ms=resp.latency_ms,
            ophamin_version=__version__,
        )
        call_path = str(persist_call(rec, proofs_root=proofs_root))

    return AdapterGenResult(
        source=source,
        model=mc.model,
        runtime=client.runtime_hint,
        latency_ms=resp.latency_ms,
        call_record_path=call_path,
    )
