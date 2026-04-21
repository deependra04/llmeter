"""OpenTelemetry GenAI bridge — exercised with an in-memory fake tracer so
the CI matrix doesn't need the opentelemetry-api package installed."""
from __future__ import annotations

import time

import pytest

from tokenly import otel


class _FakeSpan:
    def __init__(self, store: dict, name: str, start_time: int | None) -> None:
        self.store = store
        self.store["__name"] = name
        self.store["__start_time"] = start_time
        self.store["__ended"] = False

    def set_attribute(self, k: str, v) -> None:
        self.store.setdefault("attrs", {})[k] = v

    def end(self, end_time: int | None = None) -> None:
        self.store["__ended"] = True
        self.store["__end_time"] = end_time


class _FakeTracer:
    def __init__(self, store: dict) -> None:
        self.store = store

    def start_span(self, name: str, start_time: int | None = None):
        return _FakeSpan(self.store, name, start_time)


@pytest.fixture(autouse=True)
def _reset_otel():
    otel.reset()
    yield
    otel.reset()


def test_emit_span_noop_when_unavailable(monkeypatch, caplog):
    # Force import failure for opentelemetry.
    import sys

    monkeypatch.setitem(sys.modules, "opentelemetry", None)
    otel.emit_span(provider="openai", model="gpt-4o-mini", input_tokens=10, output_tokens=5)
    # No raise, no tracer cached.
    assert otel._tracer is None


def test_emit_span_records_gen_ai_attributes(monkeypatch):
    store: dict = {}
    monkeypatch.setattr(otel, "_get_tracer", lambda: _FakeTracer(store))

    otel.emit_span(
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=1000,
        output_tokens=200,
        cache_read_tokens=50,
        cache_write_tokens=0,
        cost_usd=0.0012,
        latency_ms=500,
    )

    assert store["__name"] == "chat gpt-4o-mini"
    assert store["__ended"] is True
    attrs = store["attrs"]
    assert attrs["gen_ai.provider.name"] == "openai"
    assert attrs["gen_ai.request.model"] == "gpt-4o-mini"
    assert attrs["gen_ai.response.model"] == "gpt-4o-mini"
    assert attrs["gen_ai.operation.name"] == "chat"
    assert attrs["gen_ai.usage.input_tokens"] == 1000
    assert attrs["gen_ai.usage.output_tokens"] == 200
    assert attrs["tokenly.cost_usd"] == pytest.approx(0.0012)
    assert attrs["tokenly.cache_read_tokens"] == 50
    assert "tokenly.cache_write_tokens" not in attrs  # zero values are omitted
    assert attrs["tokenly.latency_ms"] == 500


def test_emit_span_start_time_reflects_latency(monkeypatch):
    store: dict = {}
    monkeypatch.setattr(otel, "_get_tracer", lambda: _FakeTracer(store))

    before = time.time_ns()
    otel.emit_span(provider="anthropic", model="claude-haiku-4-5", latency_ms=1000)
    after = time.time_ns()

    start = store["__start_time"]
    end = store["__end_time"]
    assert end - start == 1_000_000_000  # exactly 1 s in ns
    assert before - 1_000_000_000 <= start <= after


def test_core_track_emits_span_when_otel_on(monkeypatch, tmp_path):
    from tokenly import core

    # Reset global state so the test is isolated.
    core._config = core.Config()
    core._write_queue.queue.clear() if hasattr(core._write_queue, "queue") else None

    store: dict = {}
    monkeypatch.setattr(otel, "_get_tracer", lambda: _FakeTracer(store))

    core.init(db_path=tmp_path / "log.db", otel=True)
    core.track(
        provider="openai",
        model="gpt-5-mini",
        input_tokens=100,
        output_tokens=50,
        latency_ms=120,
    )

    # The span is emitted synchronously in track(), so no wait needed.
    assert store.get("__name") == "chat gpt-5-mini"
    attrs = store.get("attrs", {})
    assert attrs.get("gen_ai.provider.name") == "openai"
    assert attrs.get("gen_ai.usage.input_tokens") == 100

    core._stop_event.set()
    if core._writer_thread:
        core._writer_thread.join(timeout=2)


def test_core_track_does_not_emit_when_otel_off(monkeypatch, tmp_path):
    from tokenly import core

    core._config = core.Config()
    core._write_queue.queue.clear() if hasattr(core._write_queue, "queue") else None

    store: dict = {}
    monkeypatch.setattr(otel, "_get_tracer", lambda: _FakeTracer(store))

    core.init(db_path=tmp_path / "log.db")  # otel left unset → False
    core.track(provider="openai", model="gpt-5-mini", input_tokens=10, output_tokens=5)

    assert "__name" not in store

    core._stop_event.set()
    if core._writer_thread:
        core._writer_thread.join(timeout=2)
