---
name: cron-ops
description: "Validate a cron schedule against all Hermes profiles before creating a job, and review cross-profile cron health with the cronops CLI."
version: 0.1.0
author: local
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cron, scheduling, validation, conflicts, hermes]
---

# Cron Ops

Validate schedules and inspect cron health across **all** Hermes profiles from one command.
Jobs live in per-profile stores; `hermes cron list` only shows one profile — `cronops` sees all.

## Before creating any cron job

1. Validate the proposed expression:

   ```
   hermes cronops validate "0 9 * * *"
   ```

   - **overlap** → the new job's execution window intersects an existing agent job. Do not
     create it as-is. Use the reported `Nearest free slot`, or adjust the expression, then
     re-validate.
   - **warning** → fires within ±45 min of an existing agent job. Ask the user whether the
     near-miss is acceptable; do not silently create it.
   - **no conflicts** → safe to create with the native `hermes cron create`.

2. Need the machine-readable form (e.g. to compare slots yourself):

   ```
   hermes cronops validate "0 9 * * *" --json
   ```

   Fields: `conflicts[]` (`level`, `job_id`, `profile`, `candidate_at`, `job_at`,
   `gap_minutes`), `context[]` (script jobs near the slot — informational only),
   `recommendation` (nearest free slot, ±45 min in 5-min steps), `catch_up_missed`
   (global setting, report-only).

3. `--profile <name>` picks whose timezone interprets the expression (default: active
   profile). `--at <ISO>` pins "now" for reproducible checks.

## Routine health checks

```
hermes cronops list                 # every job in every profile
hermes cronops list --json          # same, machine-readable
hermes cronops doctor               # findings → exit 1 (usable in CI)
hermes cronops metrics <job-id>     # runs, tokens, duration, complexity
hermes cronops history <job-id>     # last 10 runs with status/delivery
hermes cronops inspect <job-id>     # one job, full detail
```

## Managing jobs

`pause` / `resume` / `delete` accept a job id and search all profiles (add `--profile` to
disambiguate). They shell out to `hermes -p <profile> cron ...` — mutations always go through
the public CLI, never direct store writes.

Rules:

- Never run `pause`/`delete` on a job the user did not explicitly name.
- `cronops validate` and `cronops doctor` are read-only; run them freely.
