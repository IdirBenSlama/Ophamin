"""OpenAI-compatible HTTP client for local LLM runtimes.

Targets the OpenAI ``/v1/chat/completions`` endpoint shape, which
both Ollama (since 0.1.34) and MLX-LM's ``mlx_lm.server`` implement.
This means the same client code works against either runtime; swap
by setting ``OPHAMIN_LLM_BASE_URL``.

Defaults to Ollama on ``http://localhost:11434/v1`` (the path Ollama
exposes its OpenAI shim at). Set ``OPHAMIN_LLM_BASE_URL`` to
``http://localhost:8080/v1`` (or wherever you run ``mlx_lm.server``)
to swap to MLX-LM.

Per the framework's no-fallback rule:

- Connection failure → :class:`LLMClientError` raised loudly. Caller
  does not silently degrade to a default response.
- Non-2xx HTTP status → :class:`LLMClientError` raised loudly with
  the response body for triage.
- Missing model on the runtime → loud-fail (typically surfaces as a
  404 from Ollama with a hint to ``ollama pull <model>``).
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


#: Default base URL. Ollama 0.1.34+ exposes the OpenAI-compat shim at
#: ``/v1`` against its native port 11434.
_DEFAULT_BASE_URL = os.environ.get(
    "OPHAMIN_LLM_BASE_URL", "http://localhost:11434/v1",
)

#: Default API key — Ollama ignores this but the OpenAI client wire
#: format requires a token-shaped header. MLX-LM ignores too.
_DEFAULT_API_KEY = os.environ.get("OPHAMIN_LLM_API_KEY", "ollama")

#: Default timeout per request (seconds). LLM generation can take a
#: while; the workhorse 70B model at 10 tok/s with 2048 max-tokens =
#: ~3.5 minutes. Bump for reasoning models or larger outputs.
_DEFAULT_TIMEOUT = float(os.environ.get("OPHAMIN_LLM_TIMEOUT_S", "600"))


class LLMClientError(RuntimeError):
    """Raised on any LLM transport / response failure.

    Carries the ``status_code`` (HTTP) and ``body_snippet`` (first
    1000 chars of the response) so the caller can branch + log.
    """

    def __init__(
        self, message: str, *, status_code: int = 0, body_snippet: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body_snippet = body_snippet


@dataclass(frozen=True)
class LLMResponse:
    """One chat-completion result.

    ``raw`` carries the full decoded JSON for callers that want
    token counts, finish-reason, etc. The hot path (``content``)
    is exposed directly.

    Reasoning models (Qwen3 reasoning, Gemma 4 reasoning, DeepSeek-R1,
    GPT-OSS in reasoning-effort=high mode, etc.) split their output
    into a separate ``reasoning_content`` channel — chain-of-thought
    in one stream, final answer in ``content``. Some local runtimes
    (LM Studio default) emit ONLY into ``reasoning_content`` for
    reasoning-tuned models, leaving ``content`` empty. ``reasoning``
    surfaces that stream so callers can decide whether to use it
    (analysis agents → yes; structured-output agents → no, because
    a chain-of-thought stream isn't valid Python or JSON).

    Strict no-fallback: the client does NOT silently substitute
    ``reasoning`` for ``content``. Each caller decides explicitly.
    """

    content: str
    model: str
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    raw: dict[str, Any]
    reasoning: str = ""


class LLMClient:
    """OpenAI-compatible chat client; talks to Ollama or MLX-LM.

    Stateless — one instance can serve many calls. Threadsafe per
    instance (urllib.request is). No retries (callers that want
    retry decide explicitly — silent retry on a deterministic
    failure would mask real misconfiguration).
    """

    def __init__(
        self,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        api_key: str = _DEFAULT_API_KEY,
        timeout_s: float = _DEFAULT_TIMEOUT,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError(
                f"base_url must be a fully-qualified http(s) URL, got {base_url!r}"
            )
        if timeout_s <= 0:
            raise ValueError(f"timeout_s must be positive, got {timeout_s}")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_s = float(timeout_s)

    @property
    def runtime_hint(self) -> str:
        """Best-effort guess at which runtime we're targeting from base_url."""
        if "11434" in self.base_url:
            return "ollama"
        if "1234" in self.base_url:
            return "lmstudio"
        if "8080" in self.base_url:
            return "mlx-lm"
        return "unknown"

    def list_models(self) -> list[str]:
        """The model ids the runtime currently serves (``GET /v1/models``).

        Ollama / LM Studio / MLX-LM all implement the OpenAI ``/v1/models``
        listing. Returns the ``id`` of each entry. Loud-fail on transport /
        shape errors per the no-fallback rule — callers that want a
        best-effort "unknown" (e.g. availability probing) catch
        :class:`LLMClientError` themselves rather than this method guessing.
        """
        url = f"{self.base_url}/models"
        req = urllib.request.Request(
            url, method="GET",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "ophamin-agentic/0.63",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310
                raw_body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body_snippet = exc.read().decode("utf-8", errors="replace")[:1000] if exc.fp else ""
            raise LLMClientError(
                f"LLM HTTP {exc.code}: {exc.reason} at {url}",
                status_code=exc.code, body_snippet=body_snippet,
            ) from exc
        except urllib.error.URLError as exc:
            raise LLMClientError(
                f"LLM transport failure at {url}: {exc.reason}. "
                f"Is the runtime up? (ollama: `ollama serve`)",
                status_code=0, body_snippet="",
            ) from exc
        try:
            data = json.loads(raw_body)
            return [str(m["id"]) for m in data.get("data", []) if "id" in m]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise LLMClientError(
                f"LLM /models response shape unexpected: {exc}. "
                f"body[:500]={raw_body[:500]!r}",
                status_code=200, body_snippet=raw_body[:1000],
            ) from exc

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.2,
        response_format: str | None = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        """Send a chat completion. Returns an :class:`LLMResponse`.

        ``response_format`` accepts ``"json_object"`` (caller wants
        JSON output) or ``None`` (free-form). How the JSON-output
        request is encoded on the wire depends on the runtime — set
        via env var ``OPHAMIN_LLM_JSON_FORMAT``:

        - ``json_object`` (default — OpenAI, Ollama, MLX-LM): emit
          ``response_format={"type":"json_object"}`` on the request.
        - ``text`` (LM Studio): emit ``{"type":"text"}`` and rely on
          system-prompt instruction for JSON output (LM Studio rejects
          ``json_object`` with HTTP 400).
        - ``none``: omit ``response_format`` entirely. Same effect as
          ``text`` for most runtimes; useful for runtimes that reject
          any ``response_format`` shape.

        Loud-fail on any transport / response error per the
        no-fallback rule.
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
        }
        if response_format == "json_object":
            wire_format = os.environ.get("OPHAMIN_LLM_JSON_FORMAT", "json_object").strip()
            if wire_format == "json_object":
                payload["response_format"] = {"type": "json_object"}
            elif wire_format == "text":
                payload["response_format"] = {"type": "text"}
            elif wire_format == "none":
                pass  # omit response_format entirely
            else:
                raise LLMClientError(
                    f"OPHAMIN_LLM_JSON_FORMAT={wire_format!r} is not one of "
                    f"{{'json_object', 'text', 'none'}}; refusing to send.",
                    status_code=0, body_snippet="",
                )
        if stop:
            payload["stop"] = list(stop)

        url = f"{self.base_url}/chat/completions"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "ophamin-agentic/0.63",
            },
        )

        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310
                raw_body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body_snippet = exc.read().decode("utf-8", errors="replace")[:1000] if exc.fp else ""
            raise LLMClientError(
                f"LLM HTTP {exc.code}: {exc.reason} at {url}",
                status_code=exc.code, body_snippet=body_snippet,
            ) from exc
        except urllib.error.URLError as exc:
            raise LLMClientError(
                f"LLM transport failure at {url}: {exc.reason}. "
                f"Is the runtime up? (ollama: `ollama serve`; "
                f"mlx-lm: `mlx_lm.server --port 8080`)",
                status_code=0, body_snippet="",
            ) from exc
        latency_ms = (time.perf_counter() - start) * 1000.0

        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise LLMClientError(
                f"LLM returned non-JSON body: {exc}",
                status_code=200, body_snippet=raw_body[:1000],
            ) from exc

        try:
            choice = data["choices"][0]
            message = choice["message"]
            # `content` can be the empty string or even null on
            # reasoning-tuned models that emit everything via
            # `reasoning_content`. Treat null as "".
            content = message.get("content") or ""
            reasoning = message.get("reasoning_content") or ""
            finish_reason = choice.get("finish_reason", "stop")
            usage = data.get("usage") or {}
            return LLMResponse(
                content=content,
                model=data.get("model", model),
                finish_reason=finish_reason,
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                latency_ms=latency_ms,
                raw=data,
                reasoning=reasoning,
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(
                f"LLM response shape unexpected: {exc}. body[:500]={raw_body[:500]!r}",
                status_code=200, body_snippet=raw_body[:1000],
            ) from exc
