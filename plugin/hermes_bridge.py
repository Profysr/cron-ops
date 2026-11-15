"""Thin wrappers over Hermes internals — the only sanctioned way this plugin reads state.

No direct file reads: profiles come from ``hermes_cli.profiles``, jobs from ``cron.jobs``,
executions from ``cron.executions``, exactly as ``hermes cron list`` / ``hermes cron runs`` do.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Optional


@contextmanager
def use_profile(profile):
    """Route every home-derived store (``jobs.json``, ``executions.db``, ``config.yaml``,
    timezone) to *profile* for the duration — the same redirect ``hermes -p <profile>``
    performs, via the context-local override the gateway itself uses."""
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override

    token = set_hermes_home_override(profile.path)
    try:
        yield
    finally:
        reset_hermes_home_override(token)


def resolve_profiles(name: Optional[str] = None):
    """``(profiles, error)`` — all profiles, or exactly one when *name* is given."""
    from hermes_cli.profiles import list_profiles

    profiles = list_profiles()
    if name is None:
        return profiles, None
    for profile in profiles:
        if profile.name == name:
            return [profile], None
    available = ", ".join(p.name for p in profiles)
    return [], f"unknown profile '{name}' (available: {available})"


def load_jobs(profile):
    """Every job in *profile*'s store (disabled included); a missing store yields ``[]``."""
    from cron.jobs import list_jobs, use_cron_store

    with use_profile(profile), use_cron_store(profile.path):
        return list_jobs(include_disabled=True)


def find_job(job_id: str, profile_name: Optional[str] = None):
    """``(profile, job, error)`` — exact-id lookup across profiles (or one when named)."""
    profiles, error = resolve_profiles(profile_name)
    if error:
        return None, None, error
    hits = []
    for profile in profiles:
        try:
            jobs = load_jobs(profile)
        except Exception:
            continue  # broken store: report via doctor, not here
        for job in jobs:
            if str(job.get("id")) == job_id:
                hits.append((profile, job))
    if not hits:
        return None, None, f"job '{job_id}' not found"
    if len(hits) > 1:
        where = ", ".join(profile.name for profile, _ in hits)
        return None, None, f"job id '{job_id}' exists in multiple profiles ({where}); use --profile"
    return hits[0][0], hits[0][1], None
