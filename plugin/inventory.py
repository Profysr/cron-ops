"""Normalize Hermes cron jobs into the flat rows ``cronops list`` shows.

Only display fields leave this module — never prompts, origins, or anything from ``.env``.
"""

from __future__ import annotations

from typing import Optional


def normalize(job: dict, profile_name: str) -> dict:
    from cron.jobs import effective_job_state

    schedule = job.get("schedule") or {}
    return {
        "id": str(job.get("id") or "?"),
        "name": str(job.get("name") or "?"),
        "profile": profile_name,
        "schedule": str(
            job.get("schedule_display")
            or schedule.get("display")
            or schedule.get("expr")
            or "?"
        ),
        "model": str(job.get("model") or "?"),
        "execution_type": "script" if job.get("no_agent") else "agent",
        "status": effective_job_state(job),
    }


def collect(profiles, status: Optional[str] = None):
    """``(rows, errors)`` — one row per ``(profile, job id)``; load failures are captured,
    never raised, so one broken store cannot blank the whole inventory."""
    from . import hermes_bridge

    rows: dict[tuple[str, str], dict] = {}
    errors: list[str] = []
    for profile in profiles:
        try:
            jobs = hermes_bridge.load_jobs(profile)
        except Exception as exc:  # corrupted/unreadable store — report, keep going
            errors.append(f"{profile.name}: {exc}")
            continue
        for job in jobs:
            row = normalize(job, profile.name)
            if status and row["status"].lower() != status.lower():
                continue
            rows.setdefault((row["profile"], row["id"]), row)
    return list(rows.values()), errors


def print_table(rows: list[dict]) -> None:
    from rich.console import Console
    from rich.table import Table

    table = Table(show_header=True, header_style="bold")
    for column in ("ID", "Name", "Profile", "Schedule", "Model", "Type", "Status"):
        table.add_column(column)
    for row in rows:
        table.add_row(
            row["id"], row["name"], row["profile"], row["schedule"],
            row["model"], row["execution_type"], row["status"],
        )
    Console().print(table)
