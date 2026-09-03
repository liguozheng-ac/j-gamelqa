"""Minimal standard-library client for the local Ollama generate API."""

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from time import perf_counter


@dataclass(frozen=True, slots=True)
class OllamaGeneration:
    """Raw generated text plus useful provider metadata."""

    raw_response: str
    latency_seconds: float
    model: str
    done: bool
    done_reason: str | None
    thinking: str | None
    total_duration: int | None
    load_duration: int | None
    prompt_eval_count: int | None
    prompt_eval_duration: int | None
    eval_count: int | None
    eval_duration: int | None


class OllamaProviderError(RuntimeError):
    """A provider/runtime failure, separate from LLM protocol failures."""

    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category


class OllamaProvider:
    """Call one fixed Ollama model without schema forcing or automatic retry."""

    def __init__(
        self,
        model: str,
        *,
        endpoint: str = "http://127.0.0.1:11434/api/generate",
        timeout_seconds: float = 120.0,
        temperature: float = 0.0,
        thinking: bool = False,
        stream: bool = False,
    ):
        self.model = model
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.thinking = thinking
        self.stream = stream

    def request_payload(self, prompt: str) -> dict[str, object]:
        """Expose the exact reproducible generation request."""
        return {
            "model": self.model,
            "prompt": prompt,
            "stream": self.stream,
            "think": self.thinking,
            "options": {"temperature": self.temperature},
        }

    def generate(self, prompt: str) -> OllamaGeneration:
        """Return the model's ordinary text response without repair or retry."""
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(self.request_payload(prompt)).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = perf_counter()
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                response_body = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OllamaProviderError(
                "http_error", f"Ollama HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            category = (
                "timeout"
                if isinstance(exc.reason, (TimeoutError, socket.timeout))
                else "connection_error"
            )
            raise OllamaProviderError(category, str(exc.reason)) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise OllamaProviderError("timeout", str(exc)) from exc
        except OSError as exc:
            raise OllamaProviderError("connection_error", str(exc)) from exc
        latency_seconds = perf_counter() - started

        try:
            payload = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaProviderError(
                "invalid_provider_response",
                "Ollama returned a non-JSON HTTP response.",
            ) from exc
        raw_response = payload.get("response")
        if not isinstance(raw_response, str):
            raise OllamaProviderError(
                "invalid_provider_response",
                "Ollama response is missing the string field 'response'.",
            )

        thinking = payload.get("thinking")
        if thinking is not None and not isinstance(thinking, str):
            thinking = str(thinking)
        return OllamaGeneration(
            raw_response=raw_response,
            latency_seconds=latency_seconds,
            model=str(payload.get("model", self.model)),
            done=bool(payload.get("done", False)),
            done_reason=payload.get("done_reason"),
            thinking=thinking,
            total_duration=payload.get("total_duration"),
            load_duration=payload.get("load_duration"),
            prompt_eval_count=payload.get("prompt_eval_count"),
            prompt_eval_duration=payload.get("prompt_eval_duration"),
            eval_count=payload.get("eval_count"),
            eval_duration=payload.get("eval_duration"),
        )
