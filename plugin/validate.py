"""Schedule validation for `cronops validate` — cross-profile conflict detection.

Compares a candidate cron expression against every **enabled agent-backed** job across ALL
profiles (the `--profile` flag only chooses whose timezone interprets the candidate).

Rules (plan.md Chunk 4):
- schedule math via ``croniter`` (declared dependency) — no hand-rolled cron parser;
  ``interval`` jobs use plain timedelta arithmetic; ``once`` jobs contribute their ``run_at``.
- everything compared as UTC instants; display stays in the job's/profile's local zone.
- **overlap** = execution windows actually intersect; **warning** = windows within ±45 min.
- occurrences: candidate and jobs each start at 3 runs, then expand to a *common horizon*
  (capped) — a fixed 3×3 comparison misses frequency-mismatched pairs (a ``*/5`` candidate
  vs a daily job fires together daily but shares no near-term occurrence).
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
# shortcut: schedule expansion is capped here (~3.5 days of every-minute jobs); rarer
# pairs (e.g. weekly candidate vs sub-5-min jobs) past the cap can be missed — raise
# only if such a pair is a real use case, croniter cost scales linearly.
_MAX_OCCURRENCES = 5000


def _parse(ts: Any) -> Optional[datetime]:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def cron_occurrences(expr: str, start: datetime, zone, count: int = CANDIDATE_RUNS):
    """Next *count* UTC instants of *expr* after *start*, rendered as *zone*'s wall clock.

    Mirrors ``cron.jobs.compute_next_run``'s wall-clock handling *and* its DST fall-back
    resolution (``jobs.py:1249-1256``): each candidate wall clock is tried at fold 0 then
    fold 1, keeping the first instant strictly after the previous one — attaching fold 0
    alone resolves a repeated autumn hour to its earlier pass and can emit an instant in
    the past (core guards against exactly that, qwen-code#11723 class).
    Raises ``croniter``'s error on a malformed expression.
    """
    from croniter import croniter

    zone = zone or start.tzinfo
    base = start.astimezone(zone).replace(tzinfo=None)
    it = croniter(expr, base)
    out = []
    prev_ts = start.timestamp()
    for _ in range(count):
        wall = it.get_next(datetime)
        picked = None
        for _ in range(2):  # both folds, then next wall — core's order (jobs.py:1251-1256)
            for fold in (0, 1):
                cand = wall.replace(tzinfo=zone, fold=fold)
                if cand.timestamp() > prev_ts:
                    picked = cand
                    break
            if picked is not None:
                break
            wall = it.get_next(datetime)
        if picked is None:
            break
        out.append(picked.astimezone(timezone.utc))
        prev_ts = picked.timestamp()
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
        if run_at is None:
            return []
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=zone or at.tzinfo)  # naive stored value: schedule zone
        return [run_at.astimezone(timezone.utc)] if run_at > at else []
    return []


def estimate_duration(profile, job_id: str) -> Optional[int]:
    """Recent p50 run duration in ms from the executions ledger; ``None`` when unknown."""
    from . import metrics

    rows = metrics.last_executions(profile, job_id, limit=10)["runs"]
    durations = sorted(r["duration_ms"] for r in rows if r["duration_ms"] is not None)
    if not durations:
        return None
    return durations[len(durations) // 2]


def _expand(fn, target: datetime, out: list[datetime], count: int) -> list[datetime]:
    """Grow *out* until its last instant reaches *target*, calling ``fn(count)`` for a
    fresh, longer list each time (×4 growth). Stops when the schedule yields no more
    (``once`` jobs) or the count cap is hit."""
    while out and out[-1] < target and count < _MAX_OCCURRENCES:
        count = min(count * 4, _MAX_OCCURRENCES)
        new = fn(count)
        if len(new) == len(out):
            break
        out = new
    return out


def window_gap(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> Optional[timedelta]:
    """Gap between two execution windows; ``None`` = they intersect (overlap)."""
    if a0 < b1 and b0 < a1:
        return None
    return (b0 - a1) if b0 >= a1 else (a0 - b1)


def _catch_up_missed() -> bool:
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

    # Phase 1: collect comparable jobs (schedules expanded in phase 2).
    entries: list[dict] = []
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
            _dur_ms = estimate_duration(profile, str(job.get("id")))
            dur = timedelta(milliseconds=_dur_ms) if _dur_ms is not None else DEFAULT_DURATION
            entries.append({
                "profile": profile, "job": job, "zone": zone, "dur": dur, "occ": occ,
                "info": {"job_id": str(job.get("id")), "name": str(job.get("name") or "?"),
                         "profile": profile.name},
                "no_agent": bool(job.get("no_agent")),
            })

    # Phase 2: grow every schedule to the common horizon — 3 fixed runs each side misses
    # frequency-mismatched pairs (see module docstring); capped, see _MAX_OCCURRENCES.
    if entries:
        target = occurrences[-1]
        for e in entries:
            if e["occ"][-1] > target:
                target = e["occ"][-1]
        try:
            occurrences = _expand(
                lambda n: cron_occurrences(expr, at, cand_zone or at.tzinfo, n),
                target, occurrences, CANDIDATE_RUNS)
        except ValueError:
            pass  # candidate cannot reach the horizon (e.g. leap-day expr): keep the 3-run preview
        for e in entries:
            try:
                e["occ"] = _expand(
                    lambda n, e=e: job_occurrences(e["job"], e["zone"], at, n),
                    target, e["occ"], CANDIDATE_RUNS)
            except Exception:
                e["occ"] = []  # unusable schedule — doctor reports it, not validate
        entries = [e for e in entries if e["occ"]]

    # Phase 3: conflicts, script-job context, recommendation input.
    for e in entries:
        profile, job, occ, dur, info = (e["profile"], e["job"], e["occ"],
                                        e["dur"], e["info"])

        if e["no_agent"]:
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
        "occurrences": [c.isoformat() for c in occurrences[:CANDIDATE_RUNS]],
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
        free = True
        for _, _, occ, dur in existing:
            for o in occ:
                gap = window_gap(slot, slot + cand_dur, o, o + dur)
                if gap is None or gap <= WARN_WINDOW:
                    free = False
                    break
            if not free:
                break
        if free:
            return slot.isoformat()
    return None
