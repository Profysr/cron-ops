# cron-ops

A Hermes plugin that treats cron as an operation, not a per-profile afterthought:
one `hermes cronops` command to inventory, validate, and manage cron jobs across
**all** Hermes profiles. `hermes cron list` only shows one profile — `cronops` sees all.

## What it does

| Command | Purpose |
|---|---|
| `cronops list [--profile] [--status]` | Every job in every profile |
| `cronops validate <expr> [--profile] [--at]` | Check a cron expression against all jobs; reports `overlap` / `warning`, suggests the nearest free slot |
| `cronops doctor` | Health sweep; exit 1 on findings (CI-usable) |
| `cronops metrics <job-id>` | Runs, tokens, duration, complexity |
| `cronops history <job-id> [--limit]` | Recent runs with status/delivery |
| `cronops inspect <job-id>` | One job, full detail |
| `cronops pause/resume/delete <job-id>` | Mutations — always via the public `hermes cron ...` CLI, never direct store writes |

Every subcommand accepts `--json` for machine-readable output.

## Layout

```
plugin/
  plugin.yaml          # manifest: name, version, python_dependencies (rich, croniter)
  cli.py               # argparse tree + dispatcher (register entry point)
  hermes_bridge.py     # profile/job resolution via Hermes APIs
  inventory.py         # cross-profile job listing
  validate.py          # cron overlap math (croniter)
  metrics.py           # execution/usage summaries
  manage.py            # inspect + mutations (shells out to `hermes cron ...`)
  skills/cron-ops/     # bundled agent skill: when to validate before creating jobs
```

## Design rules

- Hermes is the single source of truth: stores (`jobs.json`, `executions.db`, …) are
  read-only; every mutation goes through `hermes -p <profile> cron ...`.
- No Hermes core modifications, no daemons, no credentials in output.
- Dependencies are declared in `plugin.yaml` and installed by Hermes at plugin-install
  time — no plugin-local venv.

## Status

Code-only iteration (see `plan.md`); **not installed** into Hermes from this repo.
`validate` and `doctor` are read-only and safe to run freely; `pause`/`delete`
require an explicitly named job id.

## Docs

- `plan.md` — scope, verified host facts, design invariants
- `hermes-cron-operations-feasibility-report.md` — original feasibility study
- `prompt.md` — requirements for this iteration
