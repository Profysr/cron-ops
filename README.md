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
  skills/                # bundled agent skills: cron-ops (cronops CLI),
                         # cron-job-creation, cron-job-standards,
                         # cron-pitfalls, cron-output-formatter
```

## Install

Two separate pieces: the **plugin** (the `cronops` CLI) installs into one profile's
home; the **skills** install into the shared skills dir every profile reads. No
skill registration happens inside the plugin — copying the skills is the install
step.

Prerequisites: Hermes ≥ v0.22.7 with `hermes` on PATH. `$HERMES_HOME` is your
Hermes root (Windows: `%LOCALAPPDATA%\hermes`, Linux: e.g. `~/.hermes`). The
**default** profile's home is the root itself; **named** profiles live in
`$HERMES_HOME/profiles/<profile>`. Plugins resolve per-home: `hermes -p <profile>`
only sees plugins inside that profile's home.

### 1. Copy the plugin into the profile

```bash
# named profile:
mkdir -p "$HERMES_HOME/profiles/<profile>/plugins"
cp -r plugin "$HERMES_HOME/profiles/<profile>/plugins/cron-ops"
# default profile:
cp -r plugin "$HERMES_HOME/plugins/cron-ops"
```

```powershell
# named profile:
Copy-Item -Recurse plugin "$env:LOCALAPPDATA\hermes\profiles\<profile>\plugins\cron-ops"
# default profile:
Copy-Item -Recurse plugin "$env:LOCALAPPDATA\hermes\plugins\cron-ops"
```

### 2. Gate A — validate (read-only; never pass `--install-deps`)

```bash
hermes plugins validate "$HERMES_HOME/profiles/<profile>/plugins/cron-ops" --json
```

Expect `"ok": true`, exit 0. Known warnings: private core imports; unbounded
`rich`/`croniter`.

### 3. Gate B — doctor

```bash
hermes plugins doctor "$HERMES_HOME/profiles/<profile>/plugins/cron-ops" --ci
```

Exit 0; two known WARNs (unbounded dependencies).

### 4. Enable for the profile (opt-in — plugins are opt-in by default)

```bash
hermes -p <profile> plugins enable cron-ops
hermes -p <profile> plugins list --plain --no-bundled | grep cron-ops   # cron-ops  enabled  0.1.0
```

Enable writes `plugins.enabled` into **that profile's** `config.yaml` only.
Repeat steps 1–4 for each profile that should get the command.

### 5. Copy the skills (one copy serves every profile)

```bash
cp -r plugin/skills/* "$HERMES_HOME/global-skills/"
# PowerShell: Copy-Item plugin\skills\* "$env:LOCALAPPDATA\hermes\global-skills\" -Recurse
```

`$HERMES_HOME/global-skills` is listed in `skills.external_dirs` of every
profile's config, so all profiles load these skills — nothing to enable per
profile (none of them are in any `skills.disabled` list). Skills load in
**new** sessions only. If the legacy `hermes-cron-jobs` skill is installed
(`global-skills/` + `skills/devops/`), remove it there if you want these four
plus `cron-ops` to be the only authority.

### 6. Dependencies

If Gate A fails on `python dependencies` (`ModuleNotFoundError: croniter` or
`rich`), install them into the interpreter Hermes runs on — Windows:
`"%LOCALAPPDATA%\hermes\tools\python-*\python.exe" -m pip install rich croniter`.
Never use `hermes plugins validate --install-deps`.

### 7. Verify

```bash
hermes -p <profile> plugins list --plain --no-bundled | grep cron-ops  # enabled
hermes -p <profile> cronops doctor --json                              # exit 0
hermes -p <profile> skills list | grep cron-                           # 5 cron-* rows
```

### 8. Rollback

```bash
hermes -p <profile> plugins disable cron-ops
rm -rf "$HERMES_HOME/profiles/<profile>/plugins/cron-ops"   # default profile: "$HERMES_HOME/plugins/cron-ops"
rm -rf "$HERMES_HOME/global-skills"/cron-*        # the 5 copied skill dirs
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

- `UBUNTU-TESTING.md` — Phase 02: install gates + manual test plan for the Ubuntu machine (nothing runs automatically)
- `plan.md` — scope, verified host facts, design invariants
- `hermes-cron-operations-feasibility-report.md` — original feasibility study
- `prompt.md` — requirements for this iteration
