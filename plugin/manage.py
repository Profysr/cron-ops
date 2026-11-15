"""Cross-profile job management + health sweep for `cronops inspect|pause|resume|delete|doctor`.

Reads go through Hermes native APIs (same as the rest of the plugin). Mutations never touch a
store directly: they shell out to the public CLI (``hermes -p <profile> cron <verb> <id>``),
so every write path stays Hermes's own — that is the guardrail this module exists to keep.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

_MUTATION_VERBS = {"pause": "pause", "resume": "resume", "delete": "remove"}


def inspect(profile, job: dict) -> dict[str, Any]:
    """Full normalized job + last run + next run (read-only, no subprocess)."""
    from . import inventory, metrics

    row = inventory.normalize(job, profile.name)
    rows = metrics.last_executions(
        profile, row["id"], limit=1, no_agent=bool(job.get("no_agent")))["runs"]
    row["next_run_at"] = job.get("next_run_at")
    row["last_run_at"] = job.get("last_run_at")
    row["last_status"] = job.get("last_status")
    row["last_error"] = job.get("last_error")
    row["failure_streak"] = job.get("failure_streak", 0)
    row["deliver"] = job.get("deliver")
    row["timezone"] = job.get("timezone")
    row["last_run"] = rows[0] if rows else None
    return row


def run_hermes(argv: list[str], timeout: int = 60) -> tuple[int, str]:
    """``(exit_code, combined_output)`` of a public-CLI invocation."""
    exe = shutil.which("hermes")
    if not exe:
        return 127, "hermes executable not found on PATH"
    try:
        proc = subprocess.run(
            [exe, *argv], capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, f"hermes {' '.join(argv)} timed out after {timeout}s"
    except OSError as exc:
        return 126, f"failed to launch hermes: {exc}"
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def mutate(action: str, job_id: str, profile) -> dict[str, Any]:
    """Pause/resume/delete *job_id* via ``hermes -p <profile> cron <verb> <id>``."""
    verb = _MUTATION_VERBS[action]
    argv = ["-p", profile.name, "cron", verb, job_id]
    code, output = run_hermes(argv)
    return {"ok": code == 0, "profile": profile.name, "job_id": job_id,
            "hermes_output": output}


def doctor(profiles) -> dict[str, Any]:
    """Health sweep across profiles: 0 findings = healthy (exit 0), else exit 1."""
    from pathlib import Path

    from cron.jobs import effective_job_state

    from . import hermes_bridge

    findings: list[dict] = []
    seen: dict[str, list[str]] = {}  # job id -> profiles holding it

    for profile in profiles:
        if not Path(profile.path).is_dir():
            findings.append({"type": "missing_profile", "profile": profile.name,
                             "detail": f"profile path does not exist: {profile.path}"})
            continue
        try:
            jobs = hermes_bridge.load_jobs(profile)
        except Exception as exc:
            findings.append({"type": "unreadable_store", "profile": profile.name,
                             "detail": str(exc)})
            continue
        for job in jobs:
            job_id = str(job.get("id") or "?")
            seen.setdefault(job_id, []).append(profile.name)
            if effective_job_state(job) == "error":
                findings.append({"type": "job_state", "profile": profile.name,
                                 "job_id": job_id, "detail": "state=error"})
            if (job.get("failure_streak") or 0) > 0:
                findings.append({"type": "failure_streak", "profile": profile.name,
                                 "job_id": job_id,
                                 "detail": f"failure_streak={job['failure_streak']}: "
                                           f"{job.get('last_error') or 'unknown error'}"})
            if job.get("last_delivery_error"):
                findings.append({"type": "delivery_failure", "profile": profile.name,
                                 "job_id": job_id,
                                 "detail": str(job["last_delivery_error"])})

    for job_id, holders in seen.items():
        if len(holders) > 1:
            findings.append({"type": "duplicate_id", "job_id": job_id,
                             "detail": f"id present in profiles: {', '.join(holders)}"})

    return {"healthy": not findings, "profiles": [p.name for p in profiles],
            "jobs": sum(len(v) for v in seen.values()), "findings": findings}
