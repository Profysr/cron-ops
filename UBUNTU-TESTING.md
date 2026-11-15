# cron-ops — Ubuntu Manual Test Plan (Phase 02)

**Nothing in this document runs automatically.** Every command below is for you to paste
on the Ubuntu machine. The Windows session only ran unit tests + the staging gates;
the live Ubuntu pass is entirely untested by design.

Windows and Ubuntu have different live stores, so outputs will differ — that is expected.
Record the command, its output, and its exit code for each step.

---

## 0. Prerequisites

- Hermes installed on Ubuntu, `hermes` on PATH (ideally the same version as Windows: v0.22.7+).
- This repo copied to the Ubuntu machine (any path; `$REPO` below).
- Python 3 with `croniter` for the unit tests and for `validate`:
  `python3 -m pip install --user croniter` (rich is only needed for human-readable,
  non-`--json` output: `python3 -m pip install --user rich`).

## 1. Unit tests (no install, no live Hermes access)

```bash
cd "$REPO"
python3 -m unittest
```

Expected: `Ran 83 tests ... OK`, exit 0. The suite uses stubbed Hermes modules and fake
fixture ids — it never reads a real store path.

> Note: `tests/` is gitignored (commit `fe76234`). If this repo reaches Ubuntu via git,
> copy the `tests/` directory over separately, or step 1 will report `Ran 0 tests`.

## 2. Install = copy + gates (no Windows-style side effects)

```bash
cp -r "$REPO/plugin" "$HERMES_HOME/plugins/cron-ops"
```

`$HERMES_HOME` is your Hermes home (e.g. `~/.hermes`). Plugins are **opt-in**: a copied
directory does not load until enabled.

### Gate A — validate (read-only; do NOT add `--install-deps`)

```bash
hermes plugins validate "$HERMES_HOME/plugins/cron-ops" --json
echo "exit=$?"
```

Expected: `"ok": true`, exit 0, all checks pass. Two known, expected items:
- a `warnings` entry about "private core imports" (catalog rule 9) — accepted, documented;
- `isolation.verdict: "host"` with the note that `register_cli_command` is host-wired.

### Gate B — doctor

```bash
hermes plugins doctor "$HERMES_HOME/plugins/cron-ops" --ci
echo "exit=$?"
```

Expected: exit 0; two known WARNs (`rich`, `croniter` have no upper bound in
`plugin.yaml` — advisory only); `OK: runtime discovery, manifest parsing, import,
and registration passed`.

**If either gate fails: stop, capture the output, do not enable the plugin.**

## 3. Enable + smoke test

```bash
hermes plugins enable cron-ops
hermes plugins list | grep -i cron-ops          # expect: cron-ops  enabled  0.1.0
hermes cronops doctor --json
echo "exit=$?"
```

Expected: doctor JSON with `"healthy": true` (or findings from real data — exit 1 is a
legitimate result, not a crash), exit 0 or 1, never a traceback.

If you get `ModuleNotFoundError: croniter` (or `rich`), install into the interpreter
that runs hermes and retry:

```bash
head -1 "$(command -v hermes)"                  # shows which python hermes uses
<that-python> -m pip install croniter rich
```

## 4. Full command matrix (from prompt.md)

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

### Acceptance checks with expected results

**A1 — all profiles discovered, A2 — no duplicated jobs:**

```bash
hermes cronops list --json | python3 -c '
import json, sys, collections
rows = json.load(sys.stdin)
dupes = [k for k, v in collections.Counter(r["id"] for r in rows).items() if v > 1]
print("profiles:", sorted({r["profile"] for r in rows}))
print("jobs:", len(rows), "| duplicates:", dupes or "none")'
```

Expected: one line per real profile you own; `duplicates: none`.

**A3 — last 10 executions associated correctly:** pick a job that has run before and check
`history` returns ≤10 runs, newest first, each row carrying `usage_match`
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
shell out to `hermes -p <profile> cron ...` (argv list, never a store write). You can see
this in the `--json` result's `hermes_output` field.

**A6 — installs/validates without modifying Hermes core:** after the whole pass,

```bash
cd "$(dirname "$(command -v hermes)")/.."   # hermes install root, adjust as needed
git status --porcelain                      # if hermes is a git checkout: expect clean
```

Also confirm nothing new appeared: `hermes cron status` before vs after the session
should be unchanged (no new background processes — A8).

**A7 — skill discoverable:** after enable,

```bash
hermes skills list --source local | grep -i cron-ops
```

Expected: the `cron-ops` skill listed. Fallback: ask the agent to describe its cron-ops skill.

## 5. Mutation tests — strict rules

- **Only mutate a job you create for this test.** Create a throwaway job with the normal
  Hermes flow (see `hermes cron --help`), note its id, then:
  `pause` → verify paused in `hermes cron list` → `resume` → verify scheduled →
  `delete` → verify gone.
- Every mutation also gets run once with `--json` and once without.
- **Never pause/resume/delete an existing real job.** If a command errors, stop and ask.
- Unknown-id safety check (must exit 1 and must NOT invoke hermes):
  `hermes cronops pause doesnotexist01 --json`

## 6. Rollback

```bash
hermes plugins disable cron-ops       # or remove entirely:
rm -rf "$HERMES_HOME/plugins/cron-ops"
```

No Hermes core file, config, or store is ever written by this plugin; removing the
directory is a complete rollback.

## 7. Known limitations (expected behavior, not bugs)

- `history --json` shape is `{"runs": [...], "unmatched_usage_records": n}` (not a bare list).
- Schedule expansion is capped at 5000 occurrences per horizon; extremely dense candidates
  vs weekly jobs can in theory miss a pair past the cap.
- Usage correlation anchors on `finished_at` (fallback `claimed_at`); `missed`/in-flight
  rows never consume usage records; non-exact matches carry lower `confidence`.
- `--status` vocabulary: `scheduled / paused / completed / error`.
- A no-agent (script) job exactly overlapping a candidate produces no `context` entry
  (reported limitation, by design of the gap guard).
- `doctor` does not inspect `config.yaml` or schema versions.
- CPU/RAM metrics are out of v1 and reported as unknown.

## 8. What to send back

For each stage: the command, output, and exit code — especially any traceback, any gate
failure, and the acceptance-check outputs from §4. That closes Phase 02.
