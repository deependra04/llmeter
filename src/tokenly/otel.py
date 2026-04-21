"""Optional OpenTelemetry GenAI export. Requires `pip install tokenly[otel]`.

Emits one span per tracked call, following the (experimental) OpenTelemetry
GenAI semantic conventions: `gen_ai.provider.name`, `gen_ai.request.model`,
`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`. Plus a few
`tokenly.*` attributes for cost / cache / latency.

The span's start_time is reconstructed from `latency_ms` so downstream
backends (Grafana, Datadog, Honeycomb, Jaeger) see a span that actually
covers the duration of the model call, not a zero-width marker.

Import side effects: none. `opentelemetry` is imported lazily inside
`_get_tracer` so the default install path stays stdlib-only.
"""
from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger("tokenly.otel")

_tracer: Any = None
_unavailable: bool = False


def reset() -> None:
    """Test helper — forget any cached tracer / availability state."""
    global _tracer, _unavailable
    _tracer = None
    _unavailable = False


def _get_tracer() -> Any | None:
    """Return a cached tracer, or None if opentelemetry isn't installed."""
    global _tracer, _unavailable
    if _tracer is not None:
        return _tracer
    if _unavailable:
        return None
    try:
        from opentelemetry import trace  # type: ignore

        _tracer = trace.get_tracer("tokenly")
        return _tracer
    except ImportError:
        _unavailable = True
        log.warning(
            "tokenly: otel=True but the `opentelemetry` package is not installed. "
            "Install with `pip install tokenly[otel]`."
        )
        return None
    except Exception as e:
        _unavailable = True
        log.warning("tokenly: otel tracer init failed: %s", e)
        return None


def emit_span(
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: int = 0,
) -> None:
    """Emit one gen_ai span per call. Silent no-op if otel isn't available."""
    tracer = _get_tracer()
    if tracer is None:
        return
    try:
        end_ns = time.time_ns()
        start_ns = end_ns - max(0, int(latency_ms)) * 1_000_000
        span = tracer.start_span(f"chat {model}", start_time=start_ns)
        try:
            span.set_attribute("gen_ai.provider.name", str(provider))
            span.set_attribute("gen_ai.request.model", str(model))
            span.set_attribute("gen_ai.response.model", str(model))
            span.set_attribute("gen_ai.operation.name", "chat")
            span.set_attribute("gen_ai.usage.input_tokens", int(input_tokens))
            span.set_attribute("gen_ai.usage.output_tokens", int(output_tokens))
            span.set_attribute("tokenly.cost_usd", float(cost_usd))
            if cache_read_tokens:
                span.set_attribute("tokenly.cache_read_tokens", int(cache_read_tokens))
            if cache_write_tokens:
                span.set_attribute(
                    "tokenly.cache_write_tokens", int(cache_write_tokens)
                )
            if latency_ms:
                span.set_attribute("tokenly.latency_ms", int(latency_ms))
        finally:
            span.end(end_time=end_ns)
    except Exception as e:
        log.warning("tokenly: otel emit failed: %s", e)
