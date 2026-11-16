# Plan — Hermes Cron Operations Extension (`hermes cronops`)

Scope notes for this iteration (per user):
- **Phase 01 = write the code only.** No tests, no validation gates, no install — how we test is
  decided together in a later phase (the "Gate:" lines below are deferred, not phase-01 work).
- **Code lives in `plugin/`** (created). Nothing is installed into Hermes this iteration.
- **No raw store-file reads** (never open `profiles/`, `jobs.json`, `executions.db` directly) —
  only Hermes internal APIs/commands (`hermes_cli.profiles.list_profiles()`, `cron.jobs.*`,
  `hermes ...` CLI) for long-term support.
- **Libraries via manifest**: `python_dependencies: [rich, croniter]` — Hermes's own installer
  puts them in at plugin-install time. No plugin-local venv, no bootstrap code.
- **Validate = both**: a real `cronops validate` CLI command (croniter does the overlap math)
  *and* a small bundled `cron-ops` skill that tells the agent when to validate and how to
  suggest the nearest free slot.
- No modifications to Hermes core, ever.

---

## 0. Verified facts (measured on this host — do not re-discover)

| Fact | Value |
|---|---|
| Hermes version | v0.22.7 (2026.9.24), install dir `C:\Users\mprof\AppData\Local\hermes\hermes-agent` |
| `HERMES_HOME` | `C:\Users\mprof\AppData\Local\hermes` |
| Profiles | `default` (root home) + `designer`, `developer` under `$HERMES_HOME/profiles/` (only 3 here; the feasibility report's "12 profiles" was from another machine). `hermes profile list` has **no `--json`** — use its backing API `hermes_cli.profiles.list_profiles()` (structured `ProfileInfo`: name, path, is_default, ...) instead of parsing the table |
| Job store | `$HERMES_HOME/cron/jobs.json` → `{"jobs": [ ... ]}` (a **list** of job objects, not a dict) |
| Execution store | `$HERMES_HOME/cron/executions.db` — tables `executions`, `cron_incidents`. `executions` cols: `id, job_id, source, process_id, pid, process_started_at, status, handoff_pending, handoff_started_at, claimed_at, started_at, finished_at, error, delivery_outcome, scheduled_instant, progress_at` |
| Usage log | `$HERMES_HOME/cron/usage_audit.jsonl` — one JSON per LLM run: `ts, job_id, fire_id, prompt_tokens, completion_tokens, total_tokens, response_silent, deliver_target, model, duration_ms, error` |
| Delivery store | `$HERMES_HOME/cron/deliveries.db` |
| Profile stores | `$HERMES_HOME/profiles/<name>/cron/` — same layout; a profile with no jobs has **no** `jobs.json` (must handle missing file) |
| Plugin API | `register(ctx)` entry point; `ctx.register_cli_command(name, help, setup_fn, handler_fn, description)` where `setup_fn` receives an argparse subparser and `handler_fn` is wired via `set_defaults(func=...)` (verified: `hermes_cli/plugins.py:635`) |
| Plugin storage | `plugin_db("cron-ops")` → `$HERMES_HOME/plugin-data/cron-ops/data.db`, WAL, `check_same_thread=False` (verified: `plugins/plugin_storage.py:36`). Must NOT store state in the plugin install dir |
| Skill API | `ctx.register_skill(name, path)` exists — **not used** this iteration |
| Validation | `hermes plugins validate <path> [--json]` and `hermes plugins doctor <path> --ci` (doctor uses a temp `HERMES_HOME`, restores registration state — safe to run against the staging folder without installing) |
| Manifest | `plugin.yaml`: `name`, `version`, `description`, `author`; no tools/hooks declared (we register only a CLI command) |
| Cross-profile ops | Global flag `hermes -p <profile> <cmd>`; cron verbs: `list, create, edit, pause, resume, run, remove, status, runs, history, incidents, notepad, doctor, tick` |
| Timezone resolution | `hermes_time`: `HERMES_TIMEZONE` env → `timezone` in profile `config.yaml` → server-local. Jobs may carry a per-job `timezone`. Neither profile config on this host sets one explicitly |
| Reference plugin | `plugins/teams_pipeline/` — minimal native plugin: `plugin.yaml` + `__init__.py` with `register(ctx)` calling only `ctx.register_cli_command(...)` |
| Native cron APIs | `cron.jobs.list_jobs(include_disabled=True)` + `cron.jobs.use_cron_store(home)` context manager read any profile's store (missing `jobs.json` → `[]`, verified); `cron.jobs.effective_job_state(job)` for status; `cron.executions.list_executions(job_id=, limit=)` newest-first (cap 500) — same sources `hermes cron list` / `hermes cron runs` use. Mutations: `cron.jobs.pause_job / resume_job / remove_job` |
| Libraries | Declared as `python_dependencies: [rich, croniter]` in `plugin.yaml`; Hermes's PM installs them into its environment at plugin install (consent flow). `rich` already ships with Hermes core (`rich==14.3.4`); `croniter` arrives with the install. No plugin-local venv (user decision) |

Design invariants (from prompt + feasibility report):
- Hermes is the single source of truth: **read-only** access to `jobs.json` / `executions.db` /
  `usage_audit.jsonl` / `deliveries.db` (open SQLite with `file:...?mode=ro`). All mutations go
  through `hermes -p <profile> cron ...` (subprocess of the public CLI), never direct writes.
- Stdlib for logic (`json`, `argparse`, `datetime/zoneinfo`, `subprocess`); lightweight pinned
  libraries instead of custom code: `rich` for table UI, `croniter` for schedule math — both
  declared in `python_dependencies` (installed by Hermes, no venv/bootstrap).
- No daemons, no background processes, no core patches, no credentials in output.
- Every command supports `--json`; human output stays concise.
- CPU/RAM sampling stays out of v1; metrics module exposes a stable shape with
  `cpu_percent: null, ram_mb: null` reported as `unknown` so a sampler can slot in later.

### Corrections to the feasibility report
1. `jobs.json` `jobs` is a **list**, not a dictionary.
2. Host has **3** profiles (report said 12 — machine-specific, no design impact).
3. Report's `hermes plugins doctor validate` → actual command is `hermes plugins doctor [path]`.
4. Join key between `usage_audit.jsonl` (`fire_id`) and `executions.db` (`executions.id`) is
   *presumed* from observed data (job `canonical_completions` holds execution ids) — **must be
   confirmed in Chunk 2** before relying on it.

---

## Chunk 1 — Scaffold + CLI skeleton (gate: `hermes plugins doctor --ci` passes)

Files in `plugin/`:
- `plugin.yaml` — name `cron-ops`, version `0.1.0`, description, author,
  `python_dependencies: [rich, croniter]`. No tools/hooks.
- `__init__.py` — `register(ctx)`: register the `cronops` CLI command (teams_pipeline pattern)
  and the bundled `cron-ops` skill via `ctx.register_skill(...)`.
- `cli.py` — argparse tree for all subcommands: `list, validate, metrics, history, inspect,
  pause, resume, delete, doctor`. Stubs print "not implemented" and exit 0 (only `list` is
  implemented in Chunk 2); every subparser gets `--json`.
- `hermes_bridge.py` — thin wrappers over Hermes internals only: `hermes_cli.profiles.list_profiles()`
  for profiles (never scan `profiles/`), `cron.jobs.use_cron_store(profile.path)` +
  `cron.jobs.list_jobs(...)` for per-profile jobs; per-profile load errors captured, not raised.

Steps:
1. Create the folder structure in this repo.
2. Write manifest + `register(ctx)` modeled on `teams_pipeline`.
3. Gate: `hermes plugins validate cron-ops-plugin` and
   `hermes plugins doctor cron-ops-plugin --ci` (runs against the staging path; installs nothing).

Acceptance: both gates exit 0; `hermes plugins doctor` reports the `cronops` CLI command registered.

## Chunk 2 — Centralized inventory (gate: `list` matches `hermes cron list`)

Files: `inventory.py`
- `load_jobs(profile)` — `with cron.jobs.use_cron_store(profile.path): cron.jobs.list_jobs(include_disabled=True)`
  (missing store → `[]` handled natively; corrupted store → per-profile error recorded, never a
  crash). Never opens `jobs.json` directly.
- Normalize each job: `id, name, profile, schedule (expr/display/kind), model+provider,
  execution type (agent vs no_agent/script), status (enabled/paused/error → derived),
  last_run_at, last_status`.
- Dedup guard: key = `(profile, job_id)` — assert no duplicates (acceptance criterion).
- `cronops list [--profile P] [--status S] [--json]` — filters + human table.
- Secret scrub: never print `prompt`, `origin` chat ids, or anything from `.env` — only the
  declared display fields.

Gate: `cronops list --json` vs `hermes cron list` (+ `hermes -p designer cron list`) for all
3 profiles; counts and ids match.

## Chunk 3 — Execution history + metrics (gate: last-10 join verified)

Files: `metrics.py`
- Confirm join key: compare `executions.id` ↔ `usage_audit.fire_id` on real data; document the
  finding in the module docstring. Fall back to `(job_id, scheduled_instant≈ts)` window match
  if the id join does not hold.
- `last_executions(profile, job_id, limit=10)` — newest-first from `executions.db`
  (`mode=ro`), enriched with tokens/model/duration/error from `usage_audit.jsonl`
  (single streaming pass filtered by job, keep only needed fire ids — file is append-only JSONL).
- Delivery outcome from `executions.delivery_outcome` (+ `deliveries.db` only if needed).
- `complexity(total_tokens, duration_ms, no_agent)` → deterministic buckets
  (`trivial/light/moderate/heavy`) via fixed thresholds defined as module constants; no-agent
  runs classified from duration only; missing data → `unknown`.
- CPU/RAM fields present but always `unknown` in v1 (extension point documented).
- `cronops metrics <job-id> [--profile P] [--json]` — summary + complexity.
- `cronops history <job-id> [--limit N ≤10 default] [--profile P] [--json]`.
- `plugin_db("cron-ops")` gets one table `metric_cache(job_key, fetched_at, payload)` used only
  as a read-through cache for expensive rollups; Hermes stores remain authoritative.
  Include a `schema_version` table; unknown version → warn and recreate cache tables only.

Gate: for the one real job on this host (`11589b61d560`), `history --limit 10` matches
`hermes cron runs 11589b61d560 --limit 10` (ids, statuses, timestamps).

## Chunk 4 — Schedule validation (gate: conflict cases pass)

Files: `validate.py`
- Schedule math via `croniter` (declared dep): next occurrences of the candidate expression and
  of every existing job, converted to UTC instants — no hand-rolled cron parser.
  `schedule.kind == "interval"` jobs handled with plain `timedelta` math.
- Also handle `schedule.kind == "interval"` jobs (Hermes supports them).
- Timezone: per-profile tz resolution mirroring `hermes_time` order
  (profile `config.yaml` `timezone` → default profile → system local), plus per-job
  `timezone` override. Compute everything in UTC instants; only display in local tz.
- Conflict rule: for a candidate schedule, expand its next occurrences (e.g. next 3 runs) and
  compare against every existing **agent-backed** (`no_agent: false`, enabled) job across all
  profiles: flag when any pair of execution windows is within **±45 minutes**, accounting for
  an estimated execution duration (use the job's recent p50 duration from metrics, default 10 min
  when unknown). No-agent jobs never *cause* a conflict but are reported as context.
- Distinguish **warning** (near-window ±45 min) from **overlap** (actual window intersection).
- Recommendation: scan ±45 min in 5-minute steps for the nearest slot with no conflict; report it.
- `cronops validate "<expr>" [--profile P] [--at ISO] [--json]` — `--at` pins "now" for
  deterministic tests.
- Global `catch_up_missed` → report-only note, never modify.

Gate: unit tests (below) + manual spot check: validating the existing `0 */6 * * *` job's own
expression flags itself; validating an expression 20 min away warns; 6 h away passes.

## Chunk 5 — Cross-profile management + doctor (gate: read-only proof)

Files: `manage.py`
- `cronops inspect <job-id> [--profile P] [--json]` — full normalized job + last run + next run
  (read-only, no Hermes subprocess needed).
- `cronops pause|resume|delete <job-id> [--profile P]` — thin wrappers:
  `run_hermes(["-p", profile, "cron", "pause"|"resume"|"remove", job_id])`.
  Profile resolution: explicit `--profile`, else search all profiles for the id (ambiguous id →
  error listing candidates). Pass through exit code and stderr; `--json` wraps
  `{ok, profile, job_id, hermes_output}`.
- `cronops doctor [--json]` — health sweep: unreadable/malformed stores, duplicate ids,
  profiles listed but missing, jobs with `failure_streak > 0`, delivery failures, schema
  surprises. Exit code 0 = healthy, 1 = findings (for CI use).
- Guardrail test: monkeypatch `subprocess.run` in tests to assert management commands **only**
  ever invoke the `hermes` CLI (never open a store for writing).

Gate: `pause`/`resume` exercised against a **created-for-test** job next iteration (not on the
real `hub-maintenance` job); this iteration only the unit-test guardrail runs.

## Chunk 5b — Bundled `cron-ops` skill

Files: `skills/cron-ops/SKILL.md`, registered in `__init__.py` via `ctx.register_skill("cron-ops", path)`.
- Content (agent-facing, short): validate a schedule with `cronops validate "<expr>"` **before**
  creating a job; when it warns/overlaps, pull `cronops list --json`, compare, and propose the
  nearest free slot; distinguish warning vs actual overlap.

## Chunk 6 — Tests (gate: green suite)

`cron-ops-plugin/tests/` with stdlib `unittest` (runnable via `python -m unittest`):
- `test_cron.py` — next-occurrence cases incl. `*/15`, ranges, dow, interval schedules.
- `test_inventory.py` — fixture `jobs.json` (list form, dict form, missing file, malformed).
- `test_metrics.py` — join logic, last-10 ordering, complexity thresholds, unknown CPU/RAM.
- `test_validate.py` — ±45 min warn vs overlap, timezone conversion (Asia/Karachi vs UTC),
  recommendation slot, `--at` determinism.
- `test_manage.py` — profile resolution, ambiguity, subprocess-only guardrail.
- Fixtures built from **copies** of real store shapes with fake ids — no live Hermes paths in tests.

## Chunk 7 — Next iteration: install + live validation (NOT this iteration)

Deferred per user instruction; listed so nothing is forgotten:
1. Copy/install `cron-ops-plugin/` → `$HERMES_HOME/plugins/cron-ops/` (user approved testing
   via install on Windows Hermes).
2. `hermes plugins validate`, `hermes plugins doctor --ci`, `hermes plugins list`.
3. Run the full command matrix from the prompt (`list/validate/metrics/history/inspect/pause/
   resume/delete/doctor`, human + `--json`) against all 3 profiles.
4. Verify: no jobs duplicated, last-10 correct, conflicts accurate, no core files touched,
   no new background processes (`hermes cron status` unchanged before/after).
5. Write the final report: files created, commands available, validation results, limitations,
   installation instructions (prompt also asks for an Ubuntu manual-test pass — flag that the
   live stores here are Windows; Ubuntu results will differ).

## Phase 03 — Deferred enhancements (work when time permits)

Numbered to follow Phase 01 (validation report) and Phase 02 (testing — the
verification plan now lives in `README.md`). Both items reviewed 2026-11-16
against source; no code written yet — implementation starts here when time
allows.

### Limitation A — `doctor` does not inspect config.yaml or schema versions

Enhancement gap in `manage.py doctor()` (verified: it sweeps only job state,
failure streaks, delivery errors, missing/unreadable stores, duplicate ids).
Two fixes, both read-only:

1. **Config inspection** — read each profile's `config.yaml` through the
   sanctioned reader `hermes_cli.config_backend.read_config_doc_readonly()`
   (`hermes_cli/config_backend.py:406`; prefer the `_readonly` variant over
   `read_config_doc()` since doctor must never touch write/migration paths).
   - **Unexpected** cron keys (e.g. `catchup_missed` typo) → findings (exit 1).
   - **Missing** `cron.timezone` / `cron.catch_up_missed` → informational notes
     only, not findings: both have working defaults, and flagging them would
     turn every default install red, poisoning CI trust in `doctor --ci`.
2. **Schema field-presence probe** — call `list_jobs()` / `list_executions()`
   once per profile and verify expected fields (`id`, `schedule`,
   `next_run_at`, `status`). Missing fields → "schema surprise" finding
   (canary for a Hermes field rename), worded as drift, not corruption.
   Probe once per profile, never per row.

Scope: ~30–60 lines in `plugin/manage.py` + configurable config stub in
`tests/support.py` + doctor tests in `tests/test_manage.py`. Afterwards remove
the matching bullet from `README.md` § Known limitations.

### Limitation B — `usage_audit.jsonl` has no read API

Verified: writer-only in `cron/scheduler.py` (`_write_usage_audit`, line 1254);
zero readers anywhere in Hermes core. Current design stays as-is:

- **Short term (accepted):** keep the read-only streaming pass in
  `metrics.py:_usage_records()` with per-row `usage_match {method, delta_s,
  confidence}` + `unmatched_usage_records`. A heuristic is never shown as
  exact.
- **Real fix (external):** request a sanctioned read API upstream in Hermes
  core — a `read_usage_audit()`-style reader, or a `hermes cron runs --json`
  export — turning an undocumented side-channel into a stable contract.
- **Fallback (already built):** missing/unreadable file → tokens unknown,
  `usage_match: null`, unmatched counted. Do not drop the audit read entirely;
  it would discard token/model data that is available.
- **Watch item:** after any Hermes upgrade, check `unmatched_usage_records`
  drift — a jump means the record shape changed silently.

Local code work for B: none required; only the upstream request is real work.

---

## Estimated sizes
| Chunk | Effort | ~LOC |
|---|---|---|
| 1 Scaffold | 0.5 d | 150 |
| 2 Inventory | 0.5 d | 150 |
| 3 Metrics | 0.5–1 d | 200 |
| 4 Validation | 1–1.5 d | 250 |
| 5 Management/doctor | 0.5 d | 120 |
| 6 Tests | 0.5 d | 250 |
| Phase 03 Limitation A (doctor config/schema) | 0.5 d | 40–60 |
| Phase 03 Limitation B (usage-audit API) | external | 0 local |

## Out of scope (v1)
CPU/RAM sampling (v1.1), cron *creation* via `cronops` (use native `hermes cron create`), any
write to Hermes-owned stores, background daemons, modifications to Hermes core. Dependencies
limited to `rich` + `croniter` (manifest-declared); no plugin-local venv.
