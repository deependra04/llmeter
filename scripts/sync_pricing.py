"""Sync tokenly's pricing.json against the LiteLLM community pricing feed.

LiteLLM publishes a well-maintained MIT-licensed JSON at
  https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json
that the community updates when providers change prices. This script
cherry-picks updates for the models we already ship and writes a
proposed pricing.json + markdown summary.

Runs weekly via .github/workflows/pricing-sync.yml. Stdlib only.

Usage (local): `python scripts/sync_pricing.py`
Exit code 0 always. Diff is reflected in the filesystem if any.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

FEED_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)
ROOT = Path(__file__).resolve().parent.parent
PRICING_PATH = ROOT / "src" / "tokenly" / "pricing.json"
SUMMARY_PATH = ROOT / "PRICING_SYNC_SUMMARY.md"

# Map LiteLLM's `litellm_provider` values to tokenly's provider namespace.
PROVIDER_ALIASES = {
    "openai": "openai",
    "anthropic": "anthropic",
    "gemini": "google",
    "vertex_ai-language-models": "google",
    "bedrock": "anthropic",  # claude-* on bedrock, rare in practice
    "deepseek": "deepseek",
    "xai": "xai",
    "mistral": "mistral",
    "cohere_chat": "cohere",
    "cohere": "cohere",
}


def fetch_feed() -> dict:
    req = urllib.request.Request(
        FEED_URL, headers={"User-Agent": "tokenly-pricing-sync/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def to_per_million(usd_per_token: float | None) -> float | None:
    """LiteLLM stores USD per single token; we store USD per 1M tokens."""
    if usd_per_token is None:
        return None
    return round(float(usd_per_token) * 1_000_000, 6)


def normalize_key(litellm_key: str, litellm_entry: dict) -> str | None:
    """Map a LiteLLM entry to our "provider/model" key, if we can."""
    provider = litellm_entry.get("litellm_provider")
    alias = PROVIDER_ALIASES.get(provider)
    if alias is None:
        return None
    model = litellm_key
    for prefix in (
        f"{provider}/",
        "vertex_ai/",
        "bedrock/",
        "anthropic.",
        "gemini/",
    ):
        if model.startswith(prefix):
            model = model[len(prefix) :]
    return f"{alias}/{model}"


def main() -> int:
    try:
        feed = fetch_feed()
    except Exception as e:
        print(f"sync_pricing: failed to fetch feed: {e}", file=sys.stderr)
        return 0

    current: dict = json.loads(PRICING_PATH.read_text())

    # Build a lookup from the feed in our normalized key format. Later entries win.
    feed_prices: dict[str, dict] = {}
    for key, entry in feed.items():
        if not isinstance(entry, dict):
            continue
        norm = normalize_key(key, entry)
        if not norm:
            continue
        inp = to_per_million(entry.get("input_cost_per_token"))
        out = to_per_million(entry.get("output_cost_per_token"))
        cache_read = to_per_million(
            entry.get("cache_read_input_token_cost")
            or entry.get("input_cost_per_token_cache_hit")
        )
        cache_write = to_per_million(
            entry.get("cache_creation_input_token_cost")
        )
        if inp is None or out is None:
            continue
        feed_prices[norm] = {
            "input": inp,
            "output": out,
            "cache_read": cache_read,
            "cache_write": cache_write,
        }

    changes: list[str] = []
    updated = dict(current)

    for key, ours in current.items():
        theirs = feed_prices.get(key)
        if not theirs:
            continue
        new_entry = dict(ours)
        fields_changed = []
        for field in ("input", "output", "cache_read", "cache_write"):
            old = ours.get(field)
            new = theirs.get(field)
            if new is None:
                continue
            if old is None or abs(float(old) - float(new)) / max(float(new), 1e-9) > 0.005:
                fields_changed.append(f"{field}: {old} → {new}")
                new_entry[field] = new
        if fields_changed:
            updated[key] = new_entry
            changes.append(f"- **{key}**: " + ", ".join(fields_changed))

    if not changes:
        print("sync_pricing: no pricing changes detected.")
        if SUMMARY_PATH.exists():
            SUMMARY_PATH.unlink()
        return 0

    PRICING_PATH.write_text(json.dumps(updated, indent=2) + "\n")
    SUMMARY_PATH.write_text(
        "# Weekly pricing sync\n\n"
        f"Source: [{FEED_URL}]({FEED_URL}) (LiteLLM, MIT).\n\n"
        "Pricing in USD per 1M tokens.\n\n"
        "## Detected changes\n\n"
        + "\n".join(changes)
        + "\n\n"
        "_Review each line before merging. Providers occasionally restructure SKUs; "
        "LiteLLM catches most but not all of that._\n"
    )
    print(f"sync_pricing: {len(changes)} model(s) updated. See {SUMMARY_PATH}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
