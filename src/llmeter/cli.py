"""llmeter CLI: stats, tail, export, reset, doctor."""
from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
import time
from pathlib import Path

from . import __version__

_DEFAULT_DB = Path.home() / ".llmeter" / "log.db"


def _db_path() -> Path:
    return Path(os.environ.get("LLMETER_DB", str(_DEFAULT_DB))).expanduser()


def _connect() -> sqlite3.Connection:
    p = _db_path()
    if not p.exists():
        print(f"llmeter: no log at {p} yet. Run your app with `llmeter.init()` first.")
        sys.exit(0)
    return sqlite3.connect(str(p))


def _fmt_usd(x: float) -> str:
    if x < 0.01:
        return f"${x:.4f}"
    return f"${x:.2f}"


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def _window_clause(args) -> tuple[str, list]:
    if args.all:
        return "1=1", []
    if args.month:
        return "ts >= strftime('%s', 'now', 'start of month')", []
    if args.week:
        return "ts >= strftime('%s', 'now', '-7 days')", []
    return "ts >= strftime('%s', 'now', 'start of day')", []


def cmd_stats(args) -> int:
    conn = _connect()
    where, params = _window_clause(args)
    totals = conn.execute(
        f"SELECT COUNT(*), COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), "
        f"COALESCE(SUM(cache_read_tokens),0), COALESCE(SUM(cache_write_tokens),0), "
        f"COALESCE(SUM(cost_usd),0), COALESCE(AVG(latency_ms),0) "
        f"FROM calls WHERE {where}",
        params,
    ).fetchone()
    calls, in_tok, out_tok, cr_tok, cw_tok, total_cost, avg_lat = totals

    label = "All time" if args.all else ("This month" if args.month else ("Last 7 days" if args.week else "Today"))

    print()
    print(f"  llmeter · {label}")
    print("  " + "─" * 52)
    print(f"  Spend       {_fmt_usd(total_cost):>14}")
    print(f"  Calls       {_fmt_int(calls):>14}")
    print(f"  Input       {_fmt_int(in_tok):>14} tokens")
    print(f"  Output      {_fmt_int(out_tok):>14} tokens")
    if cr_tok or cw_tok:
        print(f"  Cache read  {_fmt_int(cr_tok):>14} tokens")
        if cw_tok:
            print(f"  Cache write {_fmt_int(cw_tok):>14} tokens")
    print(f"  Avg latency {int(avg_lat):>10} ms")
    print()

    by = args.by
    if by:
        if by.startswith("tag."):
            tag_key = by.split(".", 1)[1]
            rows = conn.execute(
                f"SELECT json_extract(tags, '$.{tag_key}') as k, "
                f"SUM(cost_usd), COUNT(*) FROM calls WHERE {where} "
                f"GROUP BY k ORDER BY SUM(cost_usd) DESC LIMIT 10",
                params,
            ).fetchall()
            header = f"tag:{tag_key}"
        else:
            col = {"model": "model", "provider": "provider"}.get(by, "model")
            rows = conn.execute(
                f"SELECT {col}, SUM(cost_usd), COUNT(*) FROM calls WHERE {where} "
                f"GROUP BY {col} ORDER BY SUM(cost_usd) DESC LIMIT 10",
                params,
            ).fetchall()
            header = col

        print(f"  By {header}")
        print("  " + "─" * 52)
        for name, cost, n in rows:
            name_str = str(name) if name is not None else "(none)"
            print(f"  {name_str[:32]:<32} {_fmt_usd(cost or 0):>10}  {_fmt_int(n or 0):>6} calls")
        print()

    conn.close()
    return 0


def cmd_tail(args) -> int:
    conn = _connect()
    last_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM calls").fetchone()[0]
    print("llmeter: tailing calls (Ctrl-C to stop)")
    try:
        while True:
            rows = conn.execute(
                "SELECT id, ts, provider, model, input_tokens, output_tokens, "
                "cache_read_tokens, cost_usd, latency_ms FROM calls "
                "WHERE id > ? ORDER BY id ASC",
                (last_id,),
            ).fetchall()
            for row in rows:
                rid, ts, prov, model, in_t, out_t, cr, cost, lat = row
                tstr = time.strftime("%H:%M:%S", time.localtime(ts))
                cache_str = f" cache:{cr}" if cr else ""
                print(
                    f"  {tstr}  {prov}/{model:<25} "
                    f"in:{in_t:>6} out:{out_t:>6}{cache_str} "
                    f"{_fmt_usd(cost):>10}  {lat}ms"
                )
                last_id = rid
            time.sleep(0.5)
    except KeyboardInterrupt:
        print()
    finally:
        conn.close()
    return 0


def cmd_export(args) -> int:
    conn = _connect()
    rows = conn.execute(
        "SELECT ts, provider, model, input_tokens, output_tokens, "
        "cache_read_tokens, cache_write_tokens, cost_usd, latency_ms, tags "
        "FROM calls ORDER BY ts ASC"
    ).fetchall()
    writer = csv.writer(sys.stdout)
    writer.writerow(
        [
            "ts",
            "provider",
            "model",
            "input_tokens",
            "output_tokens",
            "cache_read_tokens",
            "cache_write_tokens",
            "cost_usd",
            "latency_ms",
            "tags",
        ]
    )
    for r in rows:
        writer.writerow(r)
    conn.close()
    return 0


def cmd_reset(args) -> int:
    p = _db_path()
    if not p.exists():
        print("llmeter: no db to reset.")
        return 0
    if not args.yes:
        resp = input(f"delete {p}? [y/N] ").strip().lower()
        if resp != "y":
            print("aborted.")
            return 1
    p.unlink()
    print(f"llmeter: deleted {p}")
    return 0


def cmd_doctor(args) -> int:
    import importlib.util

    print()
    print("  llmeter · doctor")
    print("  " + "─" * 52)
    print(f"  version:  {__version__}")
    print(f"  db path:  {_db_path()}")
    print(f"  db exists: {_db_path().exists()}")
    print()
    def _has(mod: str) -> bool:
        try:
            return importlib.util.find_spec(mod) is not None
        except (ModuleNotFoundError, ValueError):
            return False

    for name, mod in [
        ("openai", "openai"),
        ("anthropic", "anthropic"),
        ("google-genai", "google.genai"),
        ("google-generativeai", "google.generativeai"),
    ]:
        mark = "ok" if _has(mod) else "not installed"
        print(f"  {name:<22} {mark}")
    print()
    for var in ["LLMETER_DB", "LLMETER_DAILY_BUDGET", "LLMETER_DAILY_WARN"]:
        val = os.environ.get(var, "(unset)")
        print(f"  {var:<22} {val}")
    print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="llmeter", description="Track AI API costs.")
    p.add_argument("--version", action="version", version=f"llmeter {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("stats", help="show spend summary")
    s.add_argument("--month", action="store_true", help="this calendar month")
    s.add_argument("--week", action="store_true", help="last 7 days")
    s.add_argument("--all", action="store_true", help="all time")
    s.add_argument("--by", choices=["model", "provider"], help="group by", default=None, nargs="?")
    s.set_defaults(func=cmd_stats)

    t = sub.add_parser("tail", help="stream calls live")
    t.set_defaults(func=cmd_tail)

    e = sub.add_parser("export", help="dump calls as CSV to stdout")
    e.add_argument("--csv", action="store_true", default=True)
    e.set_defaults(func=cmd_export)

    r = sub.add_parser("reset", help="delete log db")
    r.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    r.set_defaults(func=cmd_reset)

    d = sub.add_parser("doctor", help="diagnose setup")
    d.set_defaults(func=cmd_doctor)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
