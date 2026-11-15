"""Schedule validation for `cronops validate` — cross-profile conflict detection.

Compares a candidate cron expression against every **enabled agent-backed** job across ALL
profiles (the `--profile` flag only chooses whose timezone interprets the candidate).

Rules (plan.md Chunk 4):
- schedule math via ``croniter`` (declared dependency) — no hand-rolled cron parser;
  ``interval`` jobs use plain timedelta arithmetic; ``once`` jobs contribute their ``run_at``.
- everything compared as UTC instants; display stays in the job's/profile's local zone.
- **overlap** = execution windows actually intersect; **warning** = windows within ±45 min.
- durations: recent p50 per job from the executions ledger (default 10 min when unknown);
  the candidate (no history yet) is assumed 10 min.
- no-agent (script) jobs never *cause* a conflict — reported as context only.
- recommendation: nearest slot within ±45 min (5-min steps) whose window clears every job.
- ``cron.catch_up_missed`` is reported, never modified.
"""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

WARN_WINDOW = timedelta(minutes=45)
DEFAULT_DURATION = timedelta(minutes=10)
STEP = timedelta(minutes=5)
CANDIDATE_RUNS = 3  # occurrences of the candidate expanded for comparison


def _parse(ts: Any) -> Optional[datetime]:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def cron_occurrences(expr: str, start: datetime, zone, count: int = CANDIDATE_RUNS):
    """Next *count* UTC instants of *expr* after *start*, rendered as *zone*'s wall clock.

    Mirrors ``cron.jobs.compute_next_run``'s croniter handling (naive wall clock in the
    configured zone, zone re-attached after); DST fold ambiguity is tolerated here because
    the ±45 min conflict window dwarfs the one-hour fold.
    Raises ``croniter``'s error on a malformed expression.
    """
    from croniter import croniter

    zone = zone or start.tzinfo
    base = start.astimezone(zone).replace(tzinfo=None)
    it = croniter(expr, base)
    out = []
    for _ in range(count):
        wall = it.get_next(datetime)
        out.append(wall.replace(tzinfo=zone).astimezone(timezone.utc))
    return out


def interval_occurrences(minutes: int, start: datetime, anchor: datetime,
                         count: int = CANDIDATE_RUNS):
    """Next *count* UTC instants of an interval schedule, stepping in UTC (duration-preserving)."""
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=start.tzinfo)
    step = timedelta(minutes=minutes)
    if anchor <= start:
        first = anchor + ((start - anchor) // step + 1) * step
    else:
        first = anchor
    return [first + k * step for k in range(count)]


def job_occurrences(job: dict, zone, at: datetime, count: int = CANDIDATE_RUNS) -> list[datetime]:
    """Up to *count* future UTC instants of an existing job's schedule (``[]`` when unusable)."""
    sched = job.get("schedule") or {}
    kind = sched.get("kind")
    if kind == "cron":
        expr = sched.get("expr")
        return cron_occurrences(expr, at, zone, count) if expr else []
    if kind == "interval":
        minutes = sched.get("minutes")
        if not minutes:
            return []
        anchor = (_parse(job.get("last_run_at")) or _parse(job.get("next_run_at")) or at)
        return interval_occurrences(int(minutes), at, anchor, count)
    if kind == "once":
        run_at = _parse(sched.get("run_at"))
        return [run_at.astimezone(timezone.utc)] if run_at and run_at > at else []
    return []


def estimate_duration(profile, job_id: str) -> Optional[int]:
    """Recent p50 run duration in ms from the executions ledger; ``None`` when unknown."""
    from . import metrics

    rows = metrics.last_executions(profile, job_id, limit=10)
    durations = sorted(r["duration_ms"] for r in rows if r["duration_ms"] is not None)
    if not durations:
        return None
    return durations[len(durations) // 2]


def window_gap(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> Optional[timedelta]:
    """Gap between two execution windows; ``None`` = they intersect (overlap)."""
    if a0 < b1 and b0 < a1:
        return None
    return (b0 - a1) if b0 >= a1 else (a0 - b1)


def _catch_up_missed(profile) -> bool:
    """Global ``cron.catch_up_missed`` (default true) — report-only, never modified."""
    try:
        from hermes_cli.config import load_config

        cfg = load_config() or {}
        return bool((cfg.get("cron") or {}).get("catch_up_missed", True))
    except Exception:
        return True


def validate(expr: str, profiles, candidate_profile, at: datetime) -> dict[str, Any]:
    """Full validation result as a JSON-serializable dict (raises ValueError on bad expr)."""
    from cron.jobs import effective_job_state
    from hermes_time import get_timezone

    from . import hermes_bridge

    # Candidate: whose profile interprets the expression (default: active profile).
    def candidate_ctx():
        return (hermes_bridge.use_profile(candidate_profile)
                if candidate_profile is not None else nullcontext())

    with candidate_ctx():
        cand_zone = get_timezone()
    occurrences = cron_occurrences(expr, at, cand_zone or at.tzinfo)  # raises on bad expr
    cand_dur = DEFAULT_DURATION

    conflicts: dict[tuple[str, str], dict] = {}
    context: list[dict] = []
    existing: list[tuple[Any, dict, list[datetime], int]] = []  # for the recommendation

    for profile in profiles:
        with hermes_bridge.use_profile(profile):
            profile_zone = get_timezone()
            jobs = hermes_bridge.load_jobs(profile)
        for job in jobs:
            if effective_job_state(job) != "scheduled":
                continue  # paused / completed / error never fire
            zone = None
            try:
                from cron.jobs_time import zone_for_job
                zone = zone_for_job(job)
            except Exception:
                pass
            zone = zone or profile_zone or at.tzinfo
            try:
                occ = job_occurrences(job, zone, at)
            except Exception:
                continue  # unusable schedule — doctor reports it, not validate
            if not occ:
                continue
            dur = estimate_duration(profile, str(job.get("id"))) or DEFAULT_DURATION
            info = {"job_id": str(job.get("id")), "name": str(job.get("name") or "?"),
                    "profile": profile.name}

            if job.get("no_agent"):
                # Script jobs: context only, never a conflict cause.
                for c in occurrences:
                    for o in occ:
                        gap = window_gap(c, c + cand_dur, o, o + dur)
                        if gap is not None and gap <= WARN_WINDOW:
                            context.append({**info, "job_at": o.isoformat(),
                                            "gap_minutes": round(gap.total_seconds() / 60, 1)})
                            break
                    else:
                        continue
                    break
                continue

            existing.append((profile, job, occ, dur))
            for c in occurrences:
                for o in occ:
                    gap = window_gap(c, c + cand_dur, o, o + dur)
                    if gap is None:
                        level = "overlap"
                    elif gap <= WARN_WINDOW:
                        level = "warning"
                    else:
                        continue
                    key = (profile.name, info["job_id"])
                    prev = conflicts.get(key)
                    score = -1 if gap is None else gap.total_seconds()
                    if prev is None or score < prev["_score"]:
                        conflicts[key] = {
                            **info, "level": level,
                            "candidate_at": c.isoformat(), "job_at": o.isoformat(),
                            "gap_minutes": (0.0 if gap is None
                                            else round(gap.total_seconds() / 60, 1)),
                            "_score": score,
                        }
                    break  # nearest pair per (candidate run, job) is enough

    result = {
        "expr": expr,
        "at": at.isoformat(),
        "candidate_profile": candidate_profile.name if candidate_profile else None,
        "occurrences": [c.isoformat() for c in occurrences],
        "conflicts": sorted((c for c in conflicts.values()),
                            key=lambda r: (r["level"] != "overlap", r["gap_minutes"])),
        "context": context,
    }
    for rec in result["conflicts"]:
        rec.pop("_score", None)
    with candidate_ctx():
        result["catch_up_missed"] = _catch_up_missed()
    result["recommendation"] = _recommend(occurrences[0], cand_dur, existing)
    return result


def _recommend(first: datetime, cand_dur: timedelta, existing) -> Optional[str]:
    """Nearest slot to *first* (0, ±5 … ±45 min) whose window clears every agent job."""
    offsets = [timedelta(0)]
    for k in range(1, int(WARN_WINDOW / STEP) + 1):
        offsets.append(k * STEP)
        offsets.append(-k * STEP)
    for off in offsets:
        slot = first + off
        if all(window_gap(slot, slot + cand_dur, o, o + dur) is not None
               and window_gap(slot, slot + cand_dur, o, o + dur) > WARN_WINDOW
               for _, _, occ, dur in existing for o in occ):
            return slot.isoformat()
    return None
