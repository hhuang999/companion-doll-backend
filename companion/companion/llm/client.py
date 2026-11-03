"""OpenAI-compatible transport with explicit deadlines and local JSON validation."""

import os
import threading
import time
from collections.abc import Iterator
from typing import Protocol

import httpx
from openai import OpenAI
from pydantic import BaseModel

from companion.cognition.models import Usage
from companion.core.config import LLMSettings


class LLMClient(Protocol):
    def stream_chat(
        self,
        model: str,
        messages: list[dict],
        cancel: threading.Event,
        deadline: float,
        **params: object,
    ) -> Iterator[str]: ...

    def complete_json(
        self,
        model: str,
        messages: list[dict],
        schema: type[BaseModel],
        deadline: float,
        **params: object,
    ) -> BaseModel: ...


class AihubmixClient:
    def __init__(self, settings: LLMSettings) -> None:
        key = os.environ.get(settings.api_key_env)
        if not key:
            raise ValueError(f"Missing environment variable: {settings.api_key_env}")
        self.settings = settings
        self.client = OpenAI(api_key=key, base_url=settings.base_url, max_retries=0)
        # Resolve lazy SDK resources at startup, outside first-turn latency budgets.
        self.completions = self.client.chat.completions
        self.raw_completions = self.completions.with_raw_response
        self.degradations: list[str] = []
        self._lock = threading.Lock()

    def stream_chat(
        self,
        model: str,
        messages: list[dict],
        cancel: threading.Event,
        deadline: float,
        **params: object,
    ) -> Iterator[str]:
        first_timeout = float(params.pop("first_token_timeout_s", 2.5))
        remaining = deadline - time.monotonic()
        if remaining <= 0 or cancel.is_set():
            return
        started = time.monotonic()
        first = True
        with self.completions.create(
            model=model,
            messages=messages,
            stream=True,
            extra_body={"enable_thinking": self.settings.enable_thinking}
            if model.startswith("qwen")
            else {},
            timeout=httpx.Timeout(min(first_timeout, remaining)),
            **params,
        ) as stream:
            for chunk in stream:
                now = time.monotonic()
                if cancel.is_set():
                    return
                if now >= deadline or (first and now - started > first_timeout):
                    raise TimeoutError("Model generation deadline exceeded")
                if chunk.choices and chunk.choices[0].delta.content:
                    first = False
                    yield chunk.choices[0].delta.content

    def complete_json(
        self,
        model: str,
        messages: list[dict],
        schema: type[BaseModel],
        deadline: float,
        **params: object,
    ) -> BaseModel:
        accept_late_high = params.pop("accept_late_high", False)
        usage_callback = params.pop("usage_callback", None)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("JSON request deadline exceeded before dispatch")
        response = self.raw_completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            extra_body={"enable_thinking": self.settings.enable_thinking}
            if model.startswith("qwen")
            else {},
            timeout=remaining,
            **params,
        )
        degraded = response.headers.get("X-Structured-Output-Degraded")
        if degraded:
            with self._lock:
                self.degradations.append(degraded)
        completion = response.parse()
        if usage_callback:
            usage_callback(
                Usage(
                    input_tokens=completion.usage.prompt_tokens,
                    output_tokens=completion.usage.completion_tokens,
                    source="provider",
                )
                if completion.usage
                else Usage()
            )
        result = schema.model_validate_json(completion.choices[0].message.content or "")
        if time.monotonic() > deadline:
            if accept_late_high and getattr(result, "level", None) == "high":
                return result.model_copy(update={"status": "late"})
            raise TimeoutError("JSON response arrived after deadline")
        return result

    def close(self) -> None:
        self.client.close()

    def background_client(self):
        # Separate HTTP connection pool from Talker/Risk; provider QoS is still shared.
        return AihubmixClient(self.settings)
