"""Execution history + metrics for `cronops metrics` and `cronops history`.

Data sources (all read-only):
- Runs: ``cron.executions.list_executions()`` — the same native API ``hermes cron runs`` uses.
- Tokens/model/duration per run: ``<home>/cron/usage_audit.jsonl`` streamed read-only — it has
  **no Hermes read API** (only a writer in ``cron/scheduler.py``), a user-approved exception.

Join note (verified on real data, 2026-11-15): ``usage_audit.fire_id`` does **not** equal
``executions.id`` (zero overlap), so runs are joined by ``(job_id, nearest claimed_at)``:
the audit ``ts`` is the run's finish instant (``claimed_at + duration_ms ≈ ts``), matched
within ±30 min, each audit record consumed once.

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

_MATCH_WINDOW_S = 30 * 60  # audit ts vs claimed_at


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


def last_executions(profile, job_id: str, limit: int = 10,
                    no_agent: bool = False) -> list[dict[str, Any]]:
    """Newest-first runs of *job_id*, enriched with tokens/model when an audit line matches."""
    from cron.executions import list_executions

    execs = list_executions(job_id=job_id, limit=limit)
    usage = _usage_records(profile, job_id)
    used: set[int] = set()

    rows: list[dict[str, Any]] = []
    for exc in execs:
        claimed = _parse(exc.get("claimed_at"))
        match, match_idx, best = None, -1, None
        if claimed is not None:
            for idx, rec in enumerate(usage):
                if idx in used:
                    continue
                ts = _parse(rec.get("ts"))
                if ts is None:
                    continue
                delta = abs((ts - claimed).total_seconds())
                if delta <= _MATCH_WINDOW_S and (best is None or delta < best):
                    match, match_idx, best = rec, idx, delta
        if match is not None:
            used.add(match_idx)

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
            "cpu_percent": None,  # v1: unknown, sampler slots in later
            "ram_mb": None,
        })
    return rows


def summarize(rows: list[dict[str, Any]], no_agent: bool = False) -> dict[str, Any]:
    """Aggregate a history window into the `cronops metrics` summary."""
    if not rows:
        return {"runs": 0, "complexity": "unknown", "cpu_percent": None, "ram_mb": None}
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
        "cpu_percent": None,
        "ram_mb": None,
    }
