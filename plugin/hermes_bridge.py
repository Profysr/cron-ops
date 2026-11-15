"""Thin wrappers over Hermes internals — the only sanctioned way this plugin reads state.

No direct file reads: profiles come from ``hermes_cli.profiles``, jobs from ``cron.jobs``
(routed per profile via ``use_cron_store``), exactly as ``hermes cron list`` does.
"""

from __future__ import annotations

from typing import Optional


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

    with use_cron_store(profile.path):
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
        except Exception as exc:
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
