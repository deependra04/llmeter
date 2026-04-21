# Changelog

All notable changes to llmeter are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses [SemVer](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/deependra04/llmeter/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/deependra04/llmeter/releases/tag/v0.1.0
