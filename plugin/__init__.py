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
