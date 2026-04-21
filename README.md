# tokenly

[![CI](https://github.com/deependra04/tokenly/actions/workflows/ci.yml/badge.svg)](https://github.com/deependra04/tokenly/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://pypi.org/project/tokenly/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.2.0-orange)](https://github.com/deependra04/tokenly/releases)

> One line to track every AI API cost. Sentry for AI costs. No proxy, no account, free forever.

```python
import tokenly
tokenly.init()
```

That's it. Now every OpenAI / Anthropic / Google call you make is logged — tokens, cost, latency, cache hits — to a local SQLite file.

```
$ tokenly stats

  tokenly · Today
  ────────────────────────────────────────────────────
  Spend                    $4.21
  Calls                       89
  Input               1,240,500 tokens
  Output                210,400 tokens
  Cache read             87,200 tokens
  Avg latency            842 ms
```

## Why

- Your monthly AI bill came back at $847 and you have no idea which feature caused it.
- Your bill swings 2-3× every quarter for no reason you can explain.
- Every existing tool wants you to change your base URL, run a proxy, or create an account.
- tokenly is a *tracker*, not a gateway. One line, zero config, local first.

## Install

```bash
pip install tokenly
```

Python 3.10+. Zero runtime dependencies.

## Use it

```python
import tokenly
tokenly.init()

import openai
client = openai.OpenAI()
client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "hi"}],
)
```

Then any time:

```bash
tokenly stats              # today
tokenly stats --week       # last 7 days
tokenly stats --month      # this month
tokenly stats --by=model   # group by model
tokenly tail               # live stream
tokenly export > calls.csv
tokenly doctor             # diagnose setup
```

## Tag calls by user / feature

```python
tokenly.configure(tags={"user": "alice", "feature": "chat"})
```

Then:

```bash
tokenly stats --by=tag.user
tokenly stats --by=tag.feature
```

## Budget alerts

```bash
export TOKENLY_DAILY_BUDGET=10   # raise BudgetExceeded when spend hits $10/day
export TOKENLY_DAILY_WARN=5      # warn at $5/day, keep going
```

Or in code:

```python
tokenly.init(budget_usd_day=10, warn_usd_day=5)
```

## Works with

| Provider | Tracks |
|---|---|
| OpenAI | prompt / completion tokens, cached tokens, cost |
| Anthropic | input / output tokens, cache read, cache write, cost |
| Google Gemini | prompt / output tokens, cached content tokens, cost |
| DeepSeek, xAI, Mistral, Cohere | via pricing DB; patches coming |

Because tokenly patches the underlying SDKs, **LangChain, LlamaIndex, and any other framework built on these SDKs work automatically** — no integration needed. See `examples/langchain_example.py` and `examples/llamaindex_example.py`.

## OpenTelemetry GenAI export (optional)

Emit an OpenTelemetry span per tracked call, following the [GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) (`gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`). That means tokenly plugs straight into Grafana, Datadog, Honeycomb, Jaeger, or any OTel-compatible backend — no extra integration.

```bash
pip install tokenly[otel]
```

```python
import tokenly
tokenly.init(otel=True)   # or: export TOKENLY_OTEL=1
```

Span `start_time` is reconstructed from the measured latency so backends see a span that actually covers the model call, not a zero-width marker. The GenAI semconv is still experimental upstream — we track the latest and will bump as it stabilizes.

## Where is the data?

By default: `~/.tokenly/log.db` — a single SQLite file. One table, ten columns. Move it, query it, back it up, delete it. It's yours.

### Pick any backend

SQLite is the default and needs nothing. For a team setup, point tokenly at your own MySQL or Postgres:

```bash
# One of these:
export TOKENLY_DB_URL="sqlite:///~/.tokenly/log.db"                 # default
export TOKENLY_DB_URL="mysql://user:pass@host:3306/tokenly"         # pip install tokenly[mysql]
export TOKENLY_DB_URL="postgresql://user:pass@host:5432/tokenly"    # pip install tokenly[postgres]
```

Or in code:

```python
tokenly.init(db_url="postgresql://user:pass@db.internal/tokenly")
```

The schema is created automatically on first connect. The legacy `TOKENLY_DB=/path/to.db` env var still works (treated as a SQLite path).

## Local dashboard

```bash
tokenly dashboard
```

Boots a local, read-only web dashboard on `http://127.0.0.1:8787` (auto-picks a free port if that's taken) and opens your browser. Spend cards, cost-by-model bars, cost-over-time line chart, and a live table of recent calls. Tabs for Today / Week / Month / All. Refreshes every 5 seconds.

Stdlib HTTP server, no JS framework, Chart.js via CDN. Stays zero-dep. Pass `--no-open` for headless, `--host 0.0.0.0` to expose on your LAN (no auth — only do this on trusted networks).

## vs other tools

| | tokenly | LiteLLM | Helicone | Langfuse |
|---|---|---|---|---|
| One-line setup | ✓ | ✗ | ✗ | ✗ |
| Requires URL change | ✗ | ✓ | ✓ | ✗ |
| Needs account | ✗ | ✗ | ✓ | ✓ |
| Local-first | ✓ | ~ | ✗ | ~ |
| Gateway / routing | ✗ | ✓ | ✓ | ✗ |
| Pure cost tracking | ✓ | ~ | ~ | ~ |
| Zero runtime deps | ✓ | ✗ | ✗ | ✗ |

tokenly is tracking-only by design. If you want routing, fallbacks, or an auth proxy, use LiteLLM or Portkey. If you just want to know what you're spending, use tokenly.

## Roadmap

- [x] OpenAI, Anthropic, Google auto-patch
- [x] CLI: stats, tail, export, reset, doctor
- [x] Tags and budget alerts
- [x] Streaming-response support (OpenAI, Anthropic)
- [x] Multi-DB backend: SQLite (default), MySQL, Postgres
- [x] Local web dashboard (`tokenly dashboard`)
- [x] OpenTelemetry GenAI export (`pip install tokenly[otel]`)
- [x] Weekly auto-updated pricing DB
- [ ] Node / TypeScript SDK (same storage)

## License

MIT © 2026 Deependra Vishwakarma.

Pricing numbers are best-effort; verify with the provider before basing decisions on them. Unknown models log with $0 cost; please PR them in `src/tokenly/pricing.json`.
