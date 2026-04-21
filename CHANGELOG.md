# Changelog

All notable changes to llmeter are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses [SemVer](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-04-22

### Added
- **Multi-DB storage.** SQLite remains the default (zero-dep). Optional MySQL and PostgreSQL backends behind `pip install llmeter[mysql]` / `llmeter[postgres]`. Select via `LLMETER_DB_URL` env or `llmeter.init(db_url=...)`.
- **URL-based config.** `sqlite:///path/to.db`, `mysql://user:pass@host/db`, `postgresql://user:pass@host/db`.
- **Streaming-response support** for OpenAI (`stream=True` — llmeter auto-forces `stream_options.include_usage=True` so final chunk carries usage) and Anthropic (tracks input/cache on `message_start`, output on `message_delta`).
- `llmeter doctor` now reports the resolved DB URL, backend connect status, and whether pymysql / psycopg are installed.

### Changed
- `llmeter reset` works across all backends (DELETE FROM calls for MySQL/Postgres, file-delete for SQLite).
- `stats` window queries no longer depend on SQLite's `strftime` — epoch boundaries are computed in Python and passed as parameters, which is what enables cross-DB support.

### Kept
- Legacy `LLMETER_DB` env var still works (treated as a SQLite path).
- Public API (`init`, `track`, `configure`, `BudgetExceeded`) unchanged; `init()` now accepts `db_url=` alongside existing `db_path=`.

## [0.1.0] - 2026-04-22

Initial release.

### Added
- One-line `llmeter.init()` auto-instrumentation for OpenAI, Anthropic, and Google Gemini SDKs (both legacy `google.generativeai` and new `google.genai`).
- Cache-aware token tracking: OpenAI `cached_tokens`, Anthropic `cache_read_input_tokens` / `cache_creation_input_tokens`, Google `cached_content_token_count`.
- Local SQLite log at `~/.llmeter/log.db` (override with `LLMETER_DB`), WAL mode, background writer thread — never blocks the caller.
- Static pricing DB (`pricing.json`) with 20 models at April 2026 rates.
- CLI: `stats`, `stats --week`, `stats --month`, `stats --all`, `stats --by=model|provider|tag.<key>`, `tail`, `export`, `reset`, `doctor`.
- Tag calls per user / feature via `llmeter.configure(tags={...})`.
- Budget alerts via `LLMETER_DAILY_BUDGET` (hard stop, raises `BudgetExceeded`) and `LLMETER_DAILY_WARN` (soft).
- Zero runtime dependencies. Python 3.10 / 3.11 / 3.12 / 3.13.
- CI on GitHub Actions: ruff + pytest across all four Python versions.

[Unreleased]: https://github.com/deependra04/llmeter/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/deependra04/llmeter/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/deependra04/llmeter/releases/tag/v0.1.0
