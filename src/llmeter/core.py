"""Core: config, SQLite storage, background writer, call logging."""
from __future__ import annotations

import json
import logging
import os
import queue
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .pricing import compute_cost, is_known

log = logging.getLogger("llmeter")

_DEFAULT_DB = Path.home() / ".llmeter" / "log.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    tags TEXT
);
CREATE INDEX IF NOT EXISTS idx_calls_ts ON calls(ts);
CREATE INDEX IF NOT EXISTS idx_calls_model ON calls(model);
CREATE INDEX IF NOT EXISTS idx_calls_provider ON calls(provider);
"""


class BudgetExceeded(RuntimeError):
    """Raised when a configured daily budget is exceeded."""


@dataclass
class Config:
    db_path: Path = _DEFAULT_DB
    budget_usd_day: float | None = None
    warn_usd_day: float | None = None
    tags: dict[str, Any] = field(default_factory=dict)
    initialized: bool = False
    patched: set[str] = field(default_factory=set)


_config = Config()
_write_queue: queue.Queue = queue.Queue()
_writer_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _ensure_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _writer_loop() -> None:
    conn = sqlite3.connect(str(_config.db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        while not _stop_event.is_set() or not _write_queue.empty():
            try:
                row = _write_queue.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                conn.execute(
                    "INSERT INTO calls "
                    "(ts, provider, model, input_tokens, output_tokens, "
                    "cache_read_tokens, cache_write_tokens, cost_usd, latency_ms, tags) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    row,
                )
                conn.commit()
            except Exception as e:
                log.warning("llmeter: failed to write call: %s", e)
    finally:
        conn.close()


def _start_writer() -> None:
    global _writer_thread
    if _writer_thread and _writer_thread.is_alive():
        return
    _stop_event.clear()
    _writer_thread = threading.Thread(target=_writer_loop, name="llmeter-writer", daemon=True)
    _writer_thread.start()


def _today_spend_usd() -> float:
    conn = sqlite3.connect(str(_config.db_path))
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM calls "
            "WHERE ts >= strftime('%s', 'now', 'start of day')"
        ).fetchone()
        return float(row[0] or 0.0)
    finally:
        conn.close()


def track(
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    latency_ms: int = 0,
    tags: dict[str, Any] | None = None,
) -> float:
    """Record a single LLM call. Returns computed cost in USD."""
    if not _config.initialized:
        init()

    cost = compute_cost(
        provider,
        model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )

    if not is_known(provider, model):
        log.warning(
            "llmeter: unknown model %s/%s — logged with $0 cost. "
            "PR pricing at https://github.com/deependra04/llmeter",
            provider,
            model,
        )

    merged_tags = {**_config.tags, **(tags or {})}
    tags_json = json.dumps(merged_tags) if merged_tags else None

    _write_queue.put(
        (
            time.time(),
            provider,
            model,
            int(input_tokens),
            int(output_tokens),
            int(cache_read_tokens),
            int(cache_write_tokens),
            float(cost),
            int(latency_ms),
            tags_json,
        )
    )

    if _config.budget_usd_day is not None:
        spent = _today_spend_usd() + cost
        if spent >= _config.budget_usd_day:
            raise BudgetExceeded(
                f"Daily budget ${_config.budget_usd_day:.2f} exceeded (spent ${spent:.2f})"
            )

    if _config.warn_usd_day is not None:
        spent = _today_spend_usd() + cost
        if spent >= _config.warn_usd_day:
            print(
                f"llmeter: daily spend ${spent:.2f} passed warn threshold "
                f"${_config.warn_usd_day:.2f}",
                file=sys.stderr,
            )

    return cost


def configure(
    db_path: str | Path | None = None,
    budget_usd_day: float | None = None,
    warn_usd_day: float | None = None,
    tags: dict[str, Any] | None = None,
) -> None:
    if db_path is not None:
        _config.db_path = Path(db_path).expanduser()
    elif os.environ.get("LLMETER_DB"):
        _config.db_path = Path(os.environ["LLMETER_DB"]).expanduser()

    if budget_usd_day is not None:
        _config.budget_usd_day = float(budget_usd_day)
    elif os.environ.get("LLMETER_DAILY_BUDGET"):
        _config.budget_usd_day = float(os.environ["LLMETER_DAILY_BUDGET"])

    if warn_usd_day is not None:
        _config.warn_usd_day = float(warn_usd_day)
    elif os.environ.get("LLMETER_DAILY_WARN"):
        _config.warn_usd_day = float(os.environ["LLMETER_DAILY_WARN"])

    if tags is not None:
        _config.tags = dict(tags)


def init(
    db_path: str | Path | None = None,
    budget_usd_day: float | None = None,
    warn_usd_day: float | None = None,
    tags: dict[str, Any] | None = None,
) -> None:
    """Initialize llmeter. Call once at app startup.

    Detects installed provider SDKs and patches them.
    """
    configure(db_path=db_path, budget_usd_day=budget_usd_day, warn_usd_day=warn_usd_day, tags=tags)
    _ensure_db(_config.db_path)
    _start_writer()
    _config.initialized = True

    import importlib.util

    def _has_module(name: str) -> bool:
        try:
            return importlib.util.find_spec(name) is not None
        except (ModuleNotFoundError, ValueError):
            return False

    if _has_module("openai") and "openai" not in _config.patched:
        try:
            from .providers import openai as p

            p.patch()
            _config.patched.add("openai")
        except Exception as e:
            log.warning("llmeter: failed to patch openai: %s", e)

    if _has_module("anthropic") and "anthropic" not in _config.patched:
        try:
            from .providers import anthropic as p

            p.patch()
            _config.patched.add("anthropic")
        except Exception as e:
            log.warning("llmeter: failed to patch anthropic: %s", e)

    if (_has_module("google.genai") or _has_module("google.generativeai")) and "google" not in _config.patched:
        try:
            from .providers import google as p

            p.patch()
            _config.patched.add("google")
        except Exception as e:
            log.warning("llmeter: failed to patch google: %s", e)
