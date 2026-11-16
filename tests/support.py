"""Shared Hermes stubs + fixtures so the suite runs on any machine with stdlib + croniter.

The plugin imports Hermes modules lazily inside functions, so installing these stubs
before the first call is enough. No live store path is ever read (plan Chunk 6):
fixtures copy real record shapes with fake ids.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_ZONE = ZoneInfo("Asia/Karachi")

# --- mutable per-test state (cleared by reset()) ---
PROFILES: list = []            # SimpleNamespace(name, path)
JOBS: dict[str, list] = {}     # profile name -> job records
EXECUTIONS: dict[str, list] = {}  # job id -> execution rows, newest-first (API contract)
USAGE: dict[str, list] = {}    # profile name -> audit records (written to its temp home)
BROKEN: set[str] = set()       # profile names whose store load must raise
ZONES: dict[str, ZoneInfo] = {}  # profile name -> configured timezone
CURRENT: dict[str, str] = {"profile": ""}  # profile inside use_profile()
_TEMP_DIRS: list[Path] = []


def effective_job_state(job: dict) -> str:
    """Faithful copy of cron/jobs.py:542 (tolerant, never raises)."""
    stored = str(job.get("state") or "").strip()
    if stored in {"completed", "error"}:
        return stored
    if not job.get("enabled", True):
        return "paused"
    if stored == "paused" or job.get("paused_at"):
        return "scheduled"
    return stored or "scheduled"


def zone_for_job(job_or_timezone):
    """Faithful copy of cron/jobs_time.py:114 (never raises)."""
    value = job_or_timezone.get("timezone") if isinstance(job_or_timezone, dict) \
        else job_or_timezone
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return ZoneInfo(value.strip())
    except Exception:
        return None


def add_profile(name: str, zone: ZoneInfo | None = None, missing: bool = False):
    """Register a profile backed by a fresh temp home (or a non-existent path)."""
    if missing:
        home = Path(tempfile.mkdtemp(prefix="cronops-ghost-")) / "ghost-home"
        _TEMP_DIRS.append(home.parent)
    else:
        home = Path(tempfile.mkdtemp(prefix=f"cronops-{name}-"))
        _TEMP_DIRS.append(home)
        (home / "cron").mkdir(parents=True, exist_ok=True)
    if zone is not None:
        ZONES[name] = zone
    profile = SimpleNamespace(name=name, path=str(home))
    PROFILES.append(profile)
    JOBS.setdefault(name, [])
    return profile


def set_usage(profile_name: str, records: list[dict]) -> None:
    """Write audit records to <profile home>/cron/usage_audit.jsonl (fixture shape)."""
    USAGE[profile_name] = records
    home = next(p.path for p in PROFILES if p.name == profile_name)
    lines = "\n".join(json.dumps(r) for r in records)
    (Path(home) / "cron" / "usage_audit.jsonl").write_text(lines, encoding="utf-8")


def reset() -> None:
    PROFILES.clear()
    JOBS.clear()
    EXECUTIONS.clear()
    USAGE.clear()
    BROKEN.clear()
    ZONES.clear()
    CURRENT["profile"] = ""
    while _TEMP_DIRS:
        shutil.rmtree(_TEMP_DIRS.pop(), ignore_errors=True)


def _list_executions(*, job_id, limit):
    return list(EXECUTIONS.get(str(job_id), []))[: max(1, min(int(limit), 500))]


def _load_jobs(profile):
    if profile.name in BROKEN:
        raise RuntimeError(f"Cron database corrupted and unrepairable: {profile.name}")
    return list(JOBS.get(profile.name, []))


def _install() -> None:
    if getattr(sys.modules.get("cron"), "_cronops_stub", False):
        return
    cron = types.ModuleType("cron")
    cron._cronops_stub = True
    jobs_mod = types.ModuleType("cron.jobs")
    jobs_mod.effective_job_state = effective_job_state
    jobs_time = types.ModuleType("cron.jobs_time")
    jobs_time.zone_for_job = zone_for_job
    executions = types.ModuleType("cron.executions")
    executions.list_executions = _list_executions
    cron.jobs, cron.jobs_time, cron.executions = jobs_mod, jobs_time, executions
    sys.modules.update({"cron": cron, "cron.jobs": jobs_mod,
                        "cron.jobs_time": jobs_time, "cron.executions": executions})

    hermes_time = types.ModuleType("hermes_time")
    hermes_time.get_timezone = lambda: ZONES.get(CURRENT["profile"]) or DEFAULT_ZONE
    hermes_time.now = lambda: datetime.now(timezone.utc)
    sys.modules["hermes_time"] = hermes_time

    # Deterministic catch_up_missed regardless of the host's real config.
    hc = types.ModuleType("hermes_cli.config")
    hc.load_config = lambda: {"cron": {"catch_up_missed": True}}
    hp = types.ModuleType("hermes_cli")
    hp.config = hc
    sys.modules.setdefault("hermes_cli", hp)
    sys.modules["hermes_cli.config"] = hc

    from plugin import hermes_bridge as hb

    @contextmanager
    def use_profile(profile):
        prev = CURRENT["profile"]
        CURRENT["profile"] = profile.name
        try:
            yield
        finally:
            CURRENT["profile"] = prev

    def resolve_profiles(name=None):
        if name is None:
            return list(PROFILES), None
        for p in PROFILES:
            if p.name == name:
                return [p], None
        available = ", ".join(p.name for p in PROFILES)
        return [], f"unknown profile '{name}' (available: {available})"

    hb.use_profile = use_profile
    hb.load_jobs = _load_jobs
    hb.resolve_profiles = resolve_profiles


_install()


class StubbedTestCase(unittest.TestCase):
    """Every test starts from a clean registry and removes its temp homes."""

    def setUp(self):
        reset()
        self.addCleanup(reset)
