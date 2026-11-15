"""`hermes cronops` — argparse tree and dispatcher.

All nine subcommands are implemented; `--json` on every one of them.
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

    p_val = subs.add_parser(
        "validate", help="Check a cron expression against every job in every profile")
    p_val.add_argument("expr", help='Cron expression, e.g. "0 9 * * *"')
    p_val.add_argument("--profile", help="Profile whose timezone interprets the expression")
    p_val.add_argument("--at", help="Pin 'now' as an ISO timestamp (deterministic checks)")
    p_val.add_argument("--json", action="store_true", dest="json_out",
                       help="Machine-readable output")

    for name in ("inspect", "pause", "resume", "delete"):
        p = subs.add_parser(name, help=f"{name} a job across profiles")
        p.add_argument("job_id", help="Job id (see `cronops list`)")
        p.add_argument("--profile", help="Only this profile (default: search all)")
        p.add_argument("--json", action="store_true", dest="json_out",
                       help="Machine-readable output")

    subs.add_parser("doctor", help="Health sweep across all profiles"
                    ).add_argument("--json", action="store_true", dest="json_out",
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
    if action == "validate":
        return _cmd_validate(args)
    if action == "doctor":
        return _cmd_doctor(args)
    if action in ("inspect", "pause", "resume", "delete"):
        return _cmd_manage(args, action)
    return 0  # argparse rejected anything unknown; belt-and-braces


def _cmd_manage(args: argparse.Namespace, action: str) -> int:
    from . import hermes_bridge, manage

    profile, job, error = hermes_bridge.find_job(
        args.job_id, getattr(args, "profile", None))
    if error:
        print(error)
        return 1
    if action == "inspect":
        result = manage.inspect(profile, job)
        if getattr(args, "json_out", False):
            print(json.dumps(result, indent=2))
        else:
            _print_inspect(result)
        return 0
    result = manage.mutate(action, args.job_id, profile)
    if getattr(args, "json_out", False):
        print(json.dumps(result, indent=2))
    else:
        mark = "✓" if result["ok"] else "✗"
        print(f"{mark} {action} {args.job_id} ({result['profile']})")
        if result["hermes_output"]:
            print(result["hermes_output"])
    return 0 if result["ok"] else 1


def _cmd_doctor(args: argparse.Namespace) -> int:
    from . import hermes_bridge, manage

    profiles, error = hermes_bridge.resolve_profiles(None)
    if error:
        print(error)
        return 1
    report = manage.doctor(profiles)
    if getattr(args, "json_out", False):
        print(json.dumps(report, indent=2))
        return 0 if report["healthy"] else 1
    from rich.console import Console
    from rich.table import Table

    console = Console()
    if report["healthy"]:
        console.print(f"[green]healthy[/green] — {report['jobs']} jobs across "
                      f"{len(report['profiles'])} profiles, no findings")
        return 0
    table = Table(show_header=True, header_style="bold")
    for column in ("Type", "Profile", "Job", "Detail"):
        table.add_column(column)
    for finding in report["findings"]:
        table.add_row(finding["type"], finding.get("profile", "-"),
                      finding.get("job_id", "-"), finding["detail"])
    console.print(table)
    return 1


def _print_inspect(row: dict) -> None:
    from rich.console import Console
    from rich.table import Table

    table = Table(show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    for key in ("id", "name", "profile", "schedule", "model", "execution_type", "status",
                "next_run_at", "last_run_at", "last_status", "failure_streak",
                "last_error", "deliver", "timezone"):
        value = row.get(key)
        if value not in (None, "", 0, "?"):
            table.add_row(key, str(value))
    Console().print(table)
    last = row.get("last_run")
    if last:
        Console().print(f"Last run: {last['id']} {last['status']} "
                        f"at {last['claimed_at']} ({last['complexity']})")


def _cmd_validate(args: argparse.Namespace) -> int:
    from datetime import datetime

    from hermes_time import now as hermes_now

    from . import hermes_bridge, validate as validate_mod

    profiles, error = hermes_bridge.resolve_profiles(None)
    if error:
        print(error)
        return 1
    candidate = None
    if getattr(args, "profile", None):
        candidates, error = hermes_bridge.resolve_profiles(args.profile)
        if error:
            print(error)
            return 1
        candidate = candidates[0]  # timezone interpreter only; comparison stays cross-profile
    at = hermes_now()
    if getattr(args, "at", None):
        try:
            at = datetime.fromisoformat(args.at.replace("Z", "+00:00"))
            if at.tzinfo is None:
                at = at.astimezone()
        except ValueError:
            print(f"invalid --at timestamp: {args.at}")
            return 1
    try:
        result = validate_mod.validate(args.expr, profiles, candidate, at)
    except ValueError as exc:
        print(f"invalid expression '{args.expr}': {exc}")
        return 1
    if getattr(args, "json_out", False):
        print(json.dumps(result, indent=2))
    else:
        _print_validate(result)
    return 1 if any(c["level"] == "overlap" for c in result["conflicts"]) else 0


def _print_validate(result: dict) -> None:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    console.print(f"Expression: [bold]{result['expr']}[/bold]  "
                  f"(profile: {result['candidate_profile'] or 'active'})")
    console.print("Next runs: " + ", ".join(result["occurrences"]))
    conflicts = result["conflicts"]
    if conflicts:
        table = Table(show_header=True, header_style="bold")
        for column in ("Level", "Job", "Profile", "Candidate", "Existing job", "Gap"):
            table.add_column(column)
        for rec in conflicts:
            style = "red" if rec["level"] == "overlap" else "yellow"
            table.add_row(f"[{style}]{rec['level']}[/{style}]", rec["name"], rec["profile"],
                          rec["candidate_at"], rec["job_at"], f"{rec['gap_minutes']} min")
        console.print(table)
    else:
        console.print("[green]No conflicts.[/green]")
    for rec in result["context"]:
        console.print(f"  context (script job): {rec['name']} ({rec['profile']}) "
                      f"at {rec['job_at']}, {rec['gap_minutes']} min away")
    if result.get("recommendation"):
        console.print(f"Nearest free slot: [cyan]{result['recommendation']}[/cyan]")
    if result.get("catch_up_missed"):
        console.print("note: cron.catch_up_missed is on — missed occurrences fire once late "
                      "(report-only; use `hermes cron edit` to change)")


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
