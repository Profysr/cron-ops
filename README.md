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
  skills/                # agent skills: cron-ops (cronops CLI), cron-job-creation,
                         # cron-job-standards, cron-pitfalls, cron-output-formatter
                         # (copied to $HERMES_HOME/global-skills at install time —
                         #  the plugin does not register them itself)
```

## Install

Two separate pieces: the **plugin** (the `cronops` CLI) installs into one profile's
home; the **skills** install into the shared skills dir every profile reads. No
skill registration happens inside the plugin — copying the skills is the install
step.

Prerequisites: Hermes ≥ v0.22.7 with `hermes` on PATH, and this repo on the
machine (`$REPO` below). `$HERMES_HOME` is your Hermes home (e.g. `~/.hermes`).
The **default** profile's home is the home itself; **named** profiles live in
`$HERMES_HOME/profiles/<profile>`. Plugins resolve per-home: `hermes -p <profile>`
only sees plugins inside that profile's home.

### 1. Copy the plugin into the profile

```bash
# default profile:
PLUGIN_DIR="$HERMES_HOME/plugins/cron-ops"
# named profile (drop the -p <profile> flags below):
PLUGIN_DIR="$HERMES_HOME/profiles/<profile>/plugins/cron-ops"

mkdir -p "$(dirname "$PLUGIN_DIR")"
cp -r "$REPO/plugin" "$PLUGIN_DIR"
```

### 2. Gate A — validate (read-only; never pass `--install-deps`)

```bash
hermes plugins validate "$PLUGIN_DIR" --json
echo "exit=$?"
```

Expect `"ok": true`, exit 0. Two known, accepted items: a "private core imports"
warning (catalog rule 9) and `isolation.verdict: "host"` (the `register_cli_command`
call is host-wired). If a gate fails: stop, capture the output, do not enable.

### 3. Gate B — doctor

```bash
hermes plugins doctor "$PLUGIN_DIR" --ci
echo "exit=$?"
```

Expect exit 0; two known WARNs (`rich` and `croniter` have no upper bound in
`plugin.yaml` — advisory only) and `OK: runtime discovery, manifest parsing,
import, and registration passed`.

### 4. Enable for the profile (opt-in — plugins are opt-in by default)

```bash
hermes -p <profile> plugins enable cron-ops
hermes -p <profile> plugins list --plain --no-bundled | grep cron-ops   # cron-ops  enabled  0.1.0
```

Enable writes `plugins.enabled` into **that profile's** `config.yaml` only.
Repeat steps 1–4 for each profile that should get the command. For the default
profile, drop the `-p <profile>` part.

### 5. Copy the skills (one copy serves every profile)

```bash
cp -r "$REPO"/plugin/skills/* "$HERMES_HOME/global-skills/"
```

`$HERMES_HOME/global-skills` is listed in `skills.external_dirs` of every profile's
config, so all profiles load these skills — nothing to enable per profile (none of
them are in any `skills.disabled` list). Skills load in **new** sessions only. If
the legacy `hermes-cron-jobs` skill is installed (`global-skills/` + `skills/devops/`),
remove it there if you want these four plus `cron-ops` to be the only authority.

### 6. Dependencies

Gate A's `python dependencies` check runs inside the interpreter Hermes uses. If it
fails with `ModuleNotFoundError: croniter` (or `rich`), install into that
interpreter and retry:

```bash
head -1 "$(command -v hermes)"      # shows which python hermes uses
<that-python> -m pip install croniter rich
```

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
rm -rf "$PLUGIN_DIR"
rm -rf "$HERMES_HOME/global-skills"/cron-*        # the 5 copied skill dirs
```

No Hermes core file, config, or store is ever written by this plugin — removing the
directory is a complete rollback.

## Verification (fresh Ubuntu machine)

Nothing here runs automatically — paste each command and record output + exit code.

### Unit tests (no install, no live Hermes access)

```bash
cd "$REPO"
python3 -m unittest
```

Expected: `Ran 83 tests ... OK`, exit 0. The suite uses stubbed Hermes modules and
fake fixture ids — it never reads a real store path.

> `tests/` is gitignored (commit `fe76234`). If this repo reached the machine via
> git, copy `tests/` over separately, or this reports `Ran 0 tests`.

Unit-test deps: `python3 -m pip install --user croniter` (and `rich` for
human-readable output).

### Command matrix

Run each with and without `--json` (human path needs `rich`; JSON path does not).

```bash
# Inventory
hermes cronops list
hermes cronops list --profile default
hermes cronops list --status scheduled
hermes cronops list --status paused
hermes cronops list --json

# Schedule validation (read-only, safe to run freely)
hermes cronops validate "0 9 * * *"
hermes cronops validate "0 9 * * *" --profile default
hermes cronops validate "0 9 * * *" --at 2026-11-16T12:00:00+00:00 --json   # deterministic

# Metrics / history
hermes cronops metrics <job-id> --json
hermes cronops history <job-id> --limit 10 --json

# Inspect (read-only)
hermes cronops inspect <job-id> --json

# Diagnostics
hermes cronops doctor --json
```

### Acceptance checks

**A1/A2 — all profiles discovered, no duplicated jobs:**

```bash
hermes cronops list --json | python3 -c '
import json, sys, collections
rows = json.load(sys.stdin)
dupes = [k for k, v in collections.Counter(r["id"] for r in rows).items() if v > 1]
print("profiles:", sorted({r["profile"] for r in rows}))
print("jobs:", len(rows), "| duplicates:", dupes or "none")'
```

Expected: one line per real profile you own; `duplicates: none`.

**A3 — last 10 executions associated correctly:** pick a job that has run before and
check `history` returns ≤10 runs, newest first, each row carrying `usage_match`
(`{method, delta_s, confidence}`, `exact` = within 60 s) plus the top-level
`unmatched_usage_records` count:

```bash
hermes cronops history <job-id> --limit 10 --json | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("runs:", len(d["runs"]), "| unmatched:", d["unmatched_usage_records"])
print("methods:", [r["usage_match"]["method"] for r in d["runs"]])'
```

**A4 — conflict detection accuracy:**

- `validate "0 9 * * *"` against a profile that already has a job at 09:00 →
  `conflicts[0].level: "overlap"`, exit 1.
- A 20-minute near-miss → `"warning"` with a `recommendation`, exit 1.
- A far-off slot → `conflicts: []`, exit 0.
- `--at` pinned twice with the same value → byte-identical JSON.

**A5 — cross-profile operations use Hermes-native mechanisms:** `pause`/`resume`/`delete`
shell out to `hermes -p <profile> cron ...` (argv list, never a store write). Visible
in the `--json` result's `hermes_output` field.

**A6 — no Hermes core modification:** after the whole pass,

```bash
cd "$(dirname "$(command -v hermes)")/.."   # hermes install root, adjust as needed
git status --porcelain                      # if hermes is a git checkout: expect clean
```

Also confirm nothing new appeared: `hermes cron status` before vs after the session
should be unchanged (no new background processes).

**A7 — skills discoverable:**

```bash
hermes skills list | grep -i cron-
```

Expected: the copied `cron-*` rows (source `external` — they live in
`global-skills`, not the local `skills/` dir). Fallback: ask the agent to describe
its cron-ops skill.

### Mutation tests — strict rules

- **Only mutate a job you create for this test.** Create a throwaway job with the
  normal Hermes flow (`hermes cron --help`), note its id, then: `pause` → verify
  paused in `hermes cron list` → `resume` → verify scheduled → `delete` → verify gone.
- Every mutation also gets run once with `--json` and once without.
- **Never pause/resume/delete an existing real job.** If a command errors, stop and ask.
- Unknown-id safety check (must exit 1 and must NOT invoke hermes):
  `hermes cronops pause doesnotexist01 --json`

### Known limitations (expected behavior, not bugs)

- `history --json` shape is `{"runs": [...], "unmatched_usage_records": n}` (not a bare list).
- Schedule expansion is capped at 5000 occurrences per horizon; extremely dense candidates
  vs weekly jobs can in theory miss a pair past the cap.
- Usage correlation anchors on `finished_at` (fallback `claimed_at`); `missed`/in-flight
  rows never consume usage records; non-exact matches carry lower `confidence`.
- `--status` vocabulary: `scheduled / paused / completed / error`.
- A no-agent (script) job exactly overlapping a candidate produces no `context` entry
  (reported limitation, by design of the gap guard).
- `doctor` does not inspect `config.yaml` or schema versions (deferred — see `plan.md`).
- CPU/RAM metrics are out of v1 and reported as unknown.

### What to send back

For each stage: the command, output, and exit code — especially any traceback, any
gate failure, and the acceptance-check outputs above.

## Design rules

- Hermes is the single source of truth: stores (`jobs.json`, `executions.db`, …) are
  read-only; every mutation goes through `hermes -p <profile> cron ...`.
- No Hermes core modifications, no daemons, no credentials in output.
- Dependencies are declared in `plugin.yaml` and installed by Hermes at plugin-install
  time — no plugin-local venv.

## Status

Code-only iteration (see `plan.md`); **not installed** into Hermes from this repo.
`validate` and `doctor` are read-only and safe to run freely; `pause`/`delete`
require an explicitly named job id. The install + verification steps below have
been exercised only as staging gates on the dev host — the Ubuntu pass is manual.

## Docs

- `plan.md` — scope, verified host facts, design invariants
- `hermes-cron-operations-feasibility-report.md` — original feasibility study
- `prompt.md` — requirements for this iteration
