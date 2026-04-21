"""Patch openai SDK (v1.x) to record every chat completion."""
from __future__ import annotations

import logging
import time
from typing import Any

from ..core import track

log = logging.getLogger("llmeter.openai")


def _extract_usage(response: Any) -> dict[str, int]:
    """Pull token usage from an OpenAI response object."""
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return {}

    def _get(obj, name, default=0):
        if hasattr(obj, name):
            return getattr(obj, name) or default
        if isinstance(obj, dict):
            return obj.get(name, default) or default
        return default

    input_tokens = _get(usage, "prompt_tokens", 0)
    output_tokens = _get(usage, "completion_tokens", 0)

    cache_read = 0
    details = _get(usage, "prompt_tokens_details", None)
    if details:
        cache_read = _get(details, "cached_tokens", 0)
        input_tokens = max(0, input_tokens - cache_read)

    return {
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "cache_read_tokens": int(cache_read),
        "cache_write_tokens": 0,
    }


def _extract_model(response: Any, kwargs: dict) -> str:
    model = kwargs.get("model") or getattr(response, "model", None)
    return str(model) if model else "unknown"


def patch() -> None:
    """Monkey-patch openai.resources.chat.completions.Completions.create."""
    try:
        from openai.resources.chat import completions as _cc
    except Exception as e:
        log.warning("llmeter: openai SDK shape unrecognized: %s", e)
        return

    sync_cls = getattr(_cc, "Completions", None)
    async_cls = getattr(_cc, "AsyncCompletions", None)

    if sync_cls and not getattr(sync_cls.create, "__llmeter_patched__", False):
        original = sync_cls.create

        def wrapped(self, *args, **kwargs):
            start = time.perf_counter()
            response = original(self, *args, **kwargs)
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                usage = _extract_usage(response)
                if usage:
                    track(
                        provider="openai",
                        model=_extract_model(response, kwargs),
                        latency_ms=latency_ms,
                        **usage,
                    )
            except Exception as e:
                log.warning("llmeter: openai tracking failed: %s", e)
            return response

        wrapped.__llmeter_patched__ = True
        sync_cls.create = wrapped

    if async_cls and not getattr(async_cls.create, "__llmeter_patched__", False):
        original_async = async_cls.create

        async def wrapped_async(self, *args, **kwargs):
            start = time.perf_counter()
            response = await original_async(self, *args, **kwargs)
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                usage = _extract_usage(response)
                if usage:
                    track(
                        provider="openai",
                        model=_extract_model(response, kwargs),
                        latency_ms=latency_ms,
                        **usage,
                    )
            except Exception as e:
                log.warning("llmeter: openai async tracking failed: %s", e)
            return response

        wrapped_async.__llmeter_patched__ = True
        async_cls.create = wrapped_async
