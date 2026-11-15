"""Execution history + metrics for `cronops metrics` and `cronops history`.

Data sources (all read-only):
- Runs: ``cron.executions.list_executions()`` — the same native API ``hermes cron runs`` uses.
- Tokens/model/duration per run: ``<home>/cron/usage_audit.jsonl`` streamed read-only — it has
  **no Hermes read API** (only a writer in ``cron/scheduler.py``), a user-approved exception.

Join note (verified on live data, 2026-11-16): ``usage_audit.fire_id`` can **never** equal
``executions.id`` (independent ``uuid4().hex`` — zero overlap), so correlation is heuristic
and must say so: each finished attempt is anchored at its ``finished_at`` (audit ``ts`` is
written at fire end; live delta 0–2 s), falling back to ``claimed_at``, matched within
±30 min, each audit record consumed once. ``missed``/in-flight rows are not attempts and
never consume records. Every run carries ``usage_match`` = ``{method, delta_s, confidence}``
or ``null`` (heuristic matches are never presented as exact), and audit records matched to
nothing in the displayed window are counted in ``unmatched_usage_records``.

CPU/RAM: always ``None`` ("unknown") in v1 — stable shape for a future sampler.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Complexity buckets — fixed thresholds, no LLM involved.
_TOKEN_LIGHT = 10_000
_TOKEN_MODERATE = 100_000
_TOKEN_HEAVY = 500_000
_DURATION_LIGHT_MS = 10_000
_DURATION_MODERATE_MS = 60_000
_DURATION_HEAVY_MS = 300_000

_MATCH_WINDOW_S = 30 * 60  # audit ts vs the run's anchor instant
_EXACT_MATCH_S = 60  # finished_at within a minute = same completion event, not a guess
_NON_ATTEMPT_STATUSES = {"missed", "claimed", "running"}  # no finished attempt: never consume usage


def complexity(total_tokens: Optional[int], duration_ms: Optional[int],
               no_agent: bool) -> str:
    """``trivial|light|moderate|heavy`` — tokens for agent runs, duration for scripts;
    ``unknown`` when the data is missing."""
    if no_agent or total_tokens is None:
        if duration_ms is None:
            return "unknown"
        if duration_ms < _DURATION_LIGHT_MS:
            return "trivial"
        if duration_ms < _DURATION_MODERATE_MS:
            return "light"
        if duration_ms < _DURATION_HEAVY_MS:
            return "moderate"
        return "heavy"
    if total_tokens < _TOKEN_LIGHT:
        return "trivial"
    if total_tokens < _TOKEN_MODERATE:
        return "light"
    if total_tokens < _TOKEN_HEAVY:
        return "moderate"
    return "heavy"


def _parse(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _usage_records(profile, job_id: str) -> list[dict]:
    """Audit lines for *job_id*, streamed (read-only) from the profile's usage log."""
    path = Path(profile.path) / "cron" / "usage_audit.jsonl"
    records: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue  # torn append tail — skip, never crash
                if str(rec.get("job_id")) == job_id:
                    records.append(rec)
    except OSError:
        pass  # no audit file (no LLM runs yet) → tokens stay unknown
    return records


def _anchor(exc: dict) -> tuple[Optional[datetime], Optional[str]]:
    """``(instant, method)`` to compare an audit ``ts`` against: the run's finish instant
    when known, else its claim instant; ``None`` when neither parses."""
    finished = _parse(exc.get("finished_at"))
    if finished is not None:
        return finished, "finished_at"
    claimed = _parse(exc.get("claimed_at"))
    if claimed is not None:
        return claimed, "claimed_at"
    return None, None


def last_executions(profile, job_id: str, limit: int = 10,
                    no_agent: bool = False) -> dict[str, Any]:
    """``{runs: [...], unmatched_usage_records: n}`` — newest-first runs of *job_id*.

    Each run carries ``usage_match`` (``{method, delta_s, confidence}`` or ``null``) so a
    heuristic attribution is never shown as exact; the second field counts audit records
    this window could not attribute (see module docstring for the join rules).
    """
    from cron.executions import list_executions

    from . import hermes_bridge

    with hermes_bridge.use_profile(profile):
        execs = list_executions(job_id=job_id, limit=limit)
    usage = _usage_records(profile, job_id)
    used: set[int] = set()

    rows: list[dict[str, Any]] = []
    for exc in execs:
        status = str(exc.get("status") or "?")
        match, match_idx, best, method = None, -1, None, None
        if status not in _NON_ATTEMPT_STATUSES:
            anchor, method = _anchor(exc)
            if anchor is not None:
                for idx, rec in enumerate(usage):
                    if idx in used:
                        continue
                    ts = _parse(rec.get("ts"))
                    if ts is None:
                        continue
                    delta = abs((ts - anchor).total_seconds())
                    if delta <= _MATCH_WINDOW_S and (best is None or delta < best):
                        match, match_idx, best = rec, idx, delta
        if match is not None:
            used.add(match_idx)
            usage_match = {
                "method": method,
                "delta_s": int(round(best)),
                "confidence": ("exact" if method == "finished_at"
                               and best <= _EXACT_MATCH_S else "heuristic"),
            }
        else:
            usage_match = None

        started, finished = _parse(exc.get("started_at")), _parse(exc.get("finished_at"))
        duration_ms = None
        if started and finished:
            duration_ms = int((finished - started).total_seconds() * 1000)
        elif match and match.get("duration_ms") is not None:
            duration_ms = int(match["duration_ms"])

        tokens = match.get("total_tokens") if match else None
        rows.append({
            "id": str(exc.get("id") or "?"),
            "job_id": str(exc.get("job_id") or job_id),
            "status": str(exc.get("status") or "?"),
            "claimed_at": str(exc.get("claimed_at") or "?"),
            "duration_ms": duration_ms,
            "total_tokens": int(tokens) if tokens is not None else None,
            "model": str(match.get("model")) if match and match.get("model") else None,
            "delivery_outcome": exc.get("delivery_outcome"),
            "error": exc.get("error"),
            "complexity": complexity(tokens, duration_ms, no_agent),
            "usage_match": usage_match,
            "cpu_percent": None,  # v1: unknown, sampler slots in later
            "ram_mb": None,
        })
    return {"runs": rows, "unmatched_usage_records": len(usage) - len(used)}


def summarize(rows: list[dict[str, Any]], no_agent: bool = False,
              unmatched_usage_records: int = 0) -> dict[str, Any]:
    """Aggregate a history window into the `cronops metrics` summary."""
    if not rows:
        return {"runs": 0, "complexity": "unknown", "cpu_percent": None, "ram_mb": None,
                "unmatched_usage_records": unmatched_usage_records}
    statuses: dict[str, int] = {}
    for row in rows:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    tokens = [r["total_tokens"] for r in rows if r["total_tokens"] is not None]
    durations = [r["duration_ms"] for r in rows if r["duration_ms"] is not None]
    total_tokens = sum(tokens) if tokens else None
    avg_duration = int(sum(durations) / len(durations)) if durations else None
    return {
        "runs": len(rows),
        "statuses": statuses,
        "total_tokens": total_tokens,
        "avg_tokens": int(total_tokens / len(tokens)) if tokens else None,
        "avg_duration_ms": avg_duration,
        "models": sorted({r["model"] for r in rows if r["model"]}),
        "complexity": complexity(
            int(total_tokens / len(tokens)) if tokens else None, avg_duration, no_agent),
        "unmatched_usage_records": unmatched_usage_records,
        "cpu_percent": None,
        "ram_mb": None,
    }
