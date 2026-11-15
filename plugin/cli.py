"""`hermes cronops` — argparse tree and dispatcher.

Implemented: `list`, `metrics`, `history`. The rest exist so the CLI surface is
stable and print "not implemented" (exit 0).
"""

from __future__ import annotations

import argparse
import json


def setup_cli(subparser: argparse.ArgumentParser) -> None:
    subs = subparser.add_subparsers(dest="cronops_action")

    p_list = subs.add_parser("list", help="List cron jobs across profiles")
    p_list.add_argument("--profile", help="Only this profile (default: all)")
    p_list.add_argument("--status", help="Filter by status (scheduled/paused/completed/error)")
    p_list.add_argument("--json", action="store_true", dest="json_out",
                        help="Machine-readable output")

    for name in ("metrics", "history"):
        p = subs.add_parser(name, help=f"{name} for one job (last 10 runs)")
        p.add_argument("job_id", help="Job id (see `cronops list`)")
        p.add_argument("--profile", help="Only this profile (default: search all)")
        if name == "history":
            p.add_argument("--limit", type=int, default=10,
                           help="Max runs to show (default 10)")
        p.add_argument("--json", action="store_true", dest="json_out",
                       help="Machine-readable output")

    for name in ("validate", "inspect", "pause", "resume", "delete", "doctor"):
        p = subs.add_parser(name, help=f"{name} (not implemented yet)")
        p.add_argument("--json", action="store_true", dest="json_out",
                       help="Machine-readable output")


def command(args: argparse.Namespace) -> int:
    action = getattr(args, "cronops_action", None)
    if action is None:
        print("usage: hermes cronops {list,...}")
        return 0
    if action == "list":
        return _cmd_list(args)
    if action in ("metrics", "history"):
        return _cmd_runs(args, action)
    print(f"cronops {action}: not implemented yet (phase 01)")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    from . import hermes_bridge, inventory

    profiles, error = hermes_bridge.resolve_profiles(getattr(args, "profile", None))
    if error:
        print(error)
        return 1
    rows, errors = inventory.collect(profiles, status=getattr(args, "status", None))
    for message in errors:
        print(f"warning: {message}")
    if getattr(args, "json_out", False):
        print(json.dumps(rows, indent=2))
    else:
        inventory.print_table(rows)
    return 0


def _cmd_runs(args: argparse.Namespace, action: str) -> int:
    from . import hermes_bridge, metrics

    profile, job, error = hermes_bridge.find_job(
        args.job_id, getattr(args, "profile", None))
    if error:
        print(error)
        return 1
    no_agent = bool(job.get("no_agent"))
    limit = max(1, min(getattr(args, "limit", 10), 500))
    rows = metrics.last_executions(profile, args.job_id, limit=limit, no_agent=no_agent)

    if getattr(args, "json_out", False):
        if action == "metrics":
            print(json.dumps(metrics.summarize(rows, no_agent=no_agent), indent=2))
        else:
            print(json.dumps(rows, indent=2))
        return 0
    if action == "metrics":
        _print_metrics(metrics.summarize(rows, no_agent=no_agent))
    else:
        _print_history(rows)
    return 0


def _print_metrics(summary: dict) -> None:
    from rich.console import Console
    from rich.table import Table

    table = Table(show_header=False)
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    statuses = ", ".join(f"{k}={v}" for k, v in (summary.get("statuses") or {}).items())
    table.add_row("Runs", str(summary["runs"]))
    if statuses:
        table.add_row("Statuses", statuses)
    table.add_row("Total tokens", str(summary.get("total_tokens") or "unknown"))
    table.add_row("Avg tokens", str(summary.get("avg_tokens") or "unknown"))
    table.add_row("Avg duration", _fmt_ms(summary.get("avg_duration_ms")))
    table.add_row("Models", ", ".join(summary.get("models") or []) or "unknown")
    table.add_row("Complexity", summary.get("complexity", "unknown"))
    table.add_row("CPU / RAM", "unknown (v1)")
    Console().print(table)


def _print_history(rows: list[dict]) -> None:
    from rich.console import Console
    from rich.table import Table

    if not rows:
        print("No execution attempts recorded.")
        return
    table = Table(show_header=True, header_style="bold")
    for column in ("Run ID", "Status", "Claimed", "Duration", "Tokens", "Model",
                   "Delivery", "Complexity"):
        table.add_column(column)
    for row in rows:
        table.add_row(
            row["id"], row["status"], row["claimed_at"],
            _fmt_ms(row["duration_ms"]), str(row["total_tokens"] or "unknown"),
            row["model"] or "unknown", str(row["delivery_outcome"] or "-"),
            row["complexity"],
        )
        if row.get("error"):
            table.add_row("", f"[red]{row['error']}[/red]", "", "", "", "", "", "")
    Console().print(table)


def _fmt_ms(ms) -> str:
    if ms is None:
        return "unknown"
    if ms < 1000:
        return f"{ms} ms"
    if ms < 60_000:
        return f"{ms / 1000:.1f} s"
    return f"{ms / 60_000:.1f} min"
