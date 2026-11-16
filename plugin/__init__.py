"""cron-ops: centralized cron operations across Hermes profiles."""

from __future__ import annotations

from pathlib import Path

from .cli import command, setup_cli


def register(ctx) -> None:
    ctx.register_cli_command(
        name="cronops",
        help="Centralized cron operations across profiles",
        setup_fn=setup_cli,
        handler_fn=command,
        description=(
            "List, validate, inspect, and manage cron jobs across all Hermes profiles."
        ),
    )
    ctx.register_skill(
        "cron-ops",
        Path(__file__).parent / "skills" / "cron-ops" / "SKILL.md",
        "Validate a cron schedule against all Hermes profiles before creating a job; "
        "review cross-profile cron health with the cronops CLI.",
    )
    ctx.register_skill(
        "cron-job-creation",
        Path(__file__).parent / "skills" / "cron-job-creation" / "SKILL.md",
        "Create, edit, and verify Hermes cron jobs end-to-end.",
    )
    ctx.register_skill(
        "cron-job-standards",
        Path(__file__).parent / "skills" / "cron-job-standards" / "SKILL.md",
        "Recommendations for cron schedules, flags, and frequency.",
    )
    ctx.register_skill(
        "cron-pitfalls",
        Path(__file__).parent / "skills" / "cron-pitfalls" / "SKILL.md",
        "Pitfalls and fixes for failing or misbehaving cron jobs.",
    )
    ctx.register_skill(
        "cron-output-formatter",
        Path(__file__).parent / "skills" / "cron-output-formatter" / "SKILL.md",
        "Design and format user-facing cronjob responses for chat delivery.",
    )
