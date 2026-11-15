# Build notes — cron-ops plugin (Phase 01)

What was done, in order, and every Hermes codebase file/function the plugin touches.
Verified against the live install on this host: **Hermes v0.22.7**,
`C:\Users\mprof\AppData\Local\hermes\hermes-agent`.

---

## A. Steps followed

1. **Requirements intake** — read `prompt.md` (command matrix: list, validate, metrics,
   history, inspect, pause, resume, delete, doctor) and
   `hermes-cron-operations-feasibility-report.md` (store layout, join assumptions).
2. **Fact verification against the live install** — did not trust the report:
   the real store layout under `<home>/cron/` and `<home>/profiles/<name>/cron/`,
   and that `jobs.json` holds `"jobs": [ ... ]` (a **list**, report said dict → correction).
3. **Plugin API reconnaissance** — found the CLI-registration contract and the
   reference plugin to copy (see §B.1): `register_cli_command(name, help, setup_fn,
   handler_fn, description)` and how `main.py` wires `setup_fn` → `set_defaults(func=...)`.
   Verified directory plugins import as a package (`hermes_plugins.<slug>`), so
   relative imports between our modules work.
4. **Dependency strategy** — investigated a plugin-local venv (`python_runtime:
   external`, `pm/plugin_declarations.py`, guard `EXCLUDED_DIRS`); built a test venv
   with Hermes's bundled Python to prove it *could* work. **User decision: manifest
   `python_dependencies: [rich, croniter]` instead** — both are already Hermes core
   deps (`pyproject.toml`: `rich==14.3.4`, `croniter==6.2.4`), so zero bootstrap code.
5. **Plan updated** (`plan.md`) — every decision, verified-fact row, and the two
   user rulings: phase 01 = code only (no tests/validation/install), and no raw
   store-file reads in the shipped code (native APIs/commands only).
6. **Chunks 1–2 (scaffold + inventory)** — `plugin.yaml`, `__init__.py`,
   `hermes_bridge.py`, `inventory.py`, `cli.py`. Reference pattern copied from
   `plugins/teams_pipeline/cli.py`.
7. **Chunk 3 (metrics/history)** — before writing, tested the report's join key on
   real data: `usage_audit.fire_id` vs `executions.id` → **zero overlap**, so the
   report's assumed id-join is wrong; fell back to `(job_id, nearest claimed_at ±30 min)`
   (the plan's documented fallback), recorded in `metrics.py`'s docstring.
   Also discovered `usage_audit.jsonl` has **no read API** (writer only) → asked the
   user; ruling: one read-only streaming pass is allowed (see §C).
8. **Redirect discovery (critical)** — `cron.jobs.use_cron_store(home)` only routes
   `jobs.json`. `executions.db` resolves via `get_hermes_home()` (`cron/executions.py:_connect`),
   and so do `config.yaml` and the timezone. The sanctioned per-profile redirect is
   `hermes_constants.set_hermes_home_override()` (what `hermes -p`/gateway use) →
   one context manager `hermes_bridge.use_profile()` covers stores + tz together.
9. **Chunk 4 (validate)** — confirmed `croniter`'s error hierarchy derives from
   `ValueError`; confirmed `cron.jobs.compute_next_run()` can't pin `--at` (anchors
   on `_hermes_now()`), so validate does its own croniter walk mirroring
   `compute_next_run`'s wall-clock handling. Timezone helpers: `hermes_time.get_timezone()`
   (profile) + `cron.jobs_time.zone_for_job()` (per-job pin).
10. **Chunk 5 (manage/doctor)** — checked how the real CLI mutates: `hermes_cli/cron.py:_job_action`
    → `_cron_api` → `tools.cronjob_tools.cronjob`. Kept the plan's guardrail: our
    mutations shell out to `hermes -p <profile> cron pause|resume|remove <id>`
    (verb shapes read from `hermes_cli/subcommands/cron.py`), never a direct write.
11. **Chunk 5b (skill)** — read `register_skill()`'s real signature
    (`hermes_cli/plugins_content.py`: name, path, description, frontmatter; SKILL.md
    must exist at register time) and the frontmatter format from an existing skill
    (`global-skills/hermes-cron-jobs/SKILL.md`).
12. **Sanity pass** — `py_compile` on all 7 files (syntax only — no imports of Hermes,
    no execution, no `plugins validate`/`doctor`, per phase-01 rules).

---

## B. Hermes codebase files & functions used

### B.1 Plugin wiring (how our code gets called)

| File | What we use |
|---|---|
| `hermes_cli/plugins.py:635` | `ctx.register_cli_command(name, help, setup_fn, handler_fn, description)` — the only registration we call |
| `hermes_cli/main.py:3247–3249` | wiring contract: `setup_fn(plugin_parser)` then `set_defaults(func=handler_fn)`; handler receives `args`, returns int |
| `hermes_cli/plugins_loader.py:808–833` | `_load_directory_module()` — dir plugins import as `hermes_plugins.<slug>` → relative imports (`.cli`, `.hermes_bridge`) work |
| `hermes_cli/plugins_content.py:32` | `register_skill(name, path, description, frontmatter)` — used in `__init__.py` for the bundled skill |
| `plugins/teams_pipeline/cli.py` | **reference plugin** — subparser loop + dispatcher pattern our `cli.py` copies |
| `tests/tui_gateway/test_plugin_skill_slash.py:25` | skill-path convention: `Path(__file__).parent / 'skills' / name / 'SKILL.md'` |
| `hermes_cli/plugins_loader.py:225` (`missing_python_dependencies`) + `pm/plugin_declarations.py` | how `python_dependencies` is read/installed (why the manifest approach needs no code) |

### B.2 Profiles (never scanning `profiles/`)

| File | What we use |
|---|---|
| `hermes_cli/profiles.py:974` | `list_profiles()` → `ProfileInfo(name, path, is_default, ...)`; `path` = profile home (verified at `profiles.py:930–974`) — backs `hermes_bridge.resolve_profiles()` |
| (checked) `hermes_cli/subcommands` `profile list` | has **no `--json`** → reason we call the API instead of parsing the table |

### B.3 Jobs store (`jobs.json` — never opened directly)

| File | What we use |
|---|---|
| `cron/jobs.py:192` | `use_cron_store(home)` context manager — routes a profile's job store |
| `cron/jobs.py:1377` (`load_jobs`) via `list_jobs(include_disabled=True)` | job loading; missing `jobs.json` → `[]` natively; corruption raises → caught per-profile in `inventory.collect()` |
| `cron/jobs.py:542` | `effective_job_state(job)` → `scheduled/paused/completed/error` — the `--status` filter and doctor's state check |
| `cron/jobs.py:1191` | `compute_next_run(schedule, last_run_at, timezone=)` — studied for validate; its croniter wall-clock + DST-fold handling is what `validate.cron_occurrences()` mirrors |
| `cron/jobs_time.py:114` | `zone_for_job(job)` — per-job timezone pin (validate) |
| `cron/jobs.py:2813` `_cron_config_number` + `cron/missed_runs.py:41` + `hermes_cli/config_defaults.py:1786` | how `cron.catch_up_missed` (default `true`) is read — validate reports it, never modifies |
| `cron/jobs.py` record shape | inspected **through `list_jobs()`** (scrubbing `prompt`/`origin`) to learn fields: `schedule{kind: cron\|interval\|once, expr, minutes, run_at}`, `enabled`, `no_agent`, `next_run_at`, `last_run_at`, `last_status`, `failure_streak`, `deliver`, `timezone`, `catch_up` |

### B.4 Executions (`executions.db` — never opened directly by plugin code)

| File | What we use |
|---|---|
| `cron/executions.py:640` | `list_executions(job_id=, limit=, before_claimed_at=)` — newest-first, cap 500; same source `hermes cron runs` uses → backs `metrics.last_executions()` |
| `cron/executions.py:39–40` | status vocabulary (`claimed/running/completed/failed/unknown/cancelled/missed`) — used for history display and doctor |
| `cron/executions.py:57` | `_connect()` → `get_hermes_home() / "cron" / "executions.db"` — **why** `use_profile()` (home override) is required for cross-profile reads |
| `hermes_cli/cron.py:342` (`cron_runs`) | what the native `hermes cron runs` prints (no token columns) — our `history` is a superset |

### B.5 Cross-profile redirect (the key mechanism)

| File | What we use |
|---|---|
| `hermes_constants.py:32/41` | `set_hermes_home_override()` / `reset_hermes_home_override()` — context-local, same call `hermes_cli/gateway.py:3086,3160` uses per routed profile → wrapped as `hermes_bridge.use_profile(profile)` |
| `hermes_constants.py:194` (`get_hermes_home`) / `:1269` (`get_config_path`) | follow the override → one context redirects `executions.db`, `config.yaml`, and job store together |
| `hermes_cli/AGENTS.md:149` | confirms `hermes -p` sets `HERMES_HOME` before import — our override is the in-process equivalent |

### B.6 Timezone

| File | What we use |
|---|---|
| `hermes_time.py:130/147` | `get_timezone()` / `now()` — resolution order `HERMES_TIMEZONE` → profile `config.yaml` → server-local; called inside `use_profile()` so each profile resolves its own |
| `cron/jobs_time.py:114` | `zone_for_job()` — job-level pin overrides profile zone |

### B.7 Usage audit (`usage_audit.jsonl` — the one approved file read)

| File | What we use |
|---|---|
| `cron/scheduler.py:1244/1254` | `_usage_audit_path()` / `_write_usage_audit()` — **writer only; no read API exists** (this is why the user approved a read-only streaming pass in `metrics._usage_records()`) |
| `cron/scheduler.py:2519–2531` | record fields: `ts, job_id, fire_id, prompt/completion/total_tokens, model, duration_ms, error, deliver_target` |

### B.8 Mutations (pause/resume/delete)

| File | What we use |
|---|---|
| `hermes_cli/subcommands/cron.py:188/191/206` | exact verb shapes: `pause <id>`, `resume <id>`, `remove` (aliases `rm`, `delete`) `<id>`; global `-p <profile>` |
| `hermes_cli/cron.py:876` `_job_action` → `:29` `_cron_api` → `tools/cronjob_tools.py` | what the real CLI does internally — we deliberately **don't** call it in-process; `manage.run_hermes()` shells out to `hermes -p …` instead (plan guardrail: mutations only ever go through the public CLI) |

### B.9 Dependencies & misc

| File | What we use |
|---|---|
| `pyproject.toml:52,79` | proof `rich==14.3.4` and `croniter==6.2.4` are already core deps → manifest declaration is free insurance |
| `cron/jobs.py:61` `_ensure_croniter` | how core imports croniter lazily (validate imports it directly — declared dep) |
| `hermes_cli/config_backend.py:400/406` | `read_config_doc()` / `config_exists()` — the sanctioned config readers (used by Hermes itself for profile config) |
| `global-skills/hermes-cron-jobs/SKILL.md` | frontmatter format model for our `skills/cron-ops/SKILL.md` |

---

## C. The store-layout answer (ChatGPT) vs. what this plugin actually does

The layout table in that answer is **correct** — it matches what we verified in step 2
(profile-scoped `cron/` dirs; `jobs.json` = definitions, not traces; correlate a run via
`executions.db` then `usage_audit.jsonl`/`deliveries.db`).

But the advice *"your extension should read these stores across all profiles"* is where
we deliberately diverged — per your rule (**use Hermes internal APIs/commands for long-term
support**):

| Store | ChatGPT's way | What cron-ops does | Why |
|---|---|---|---|
| `jobs.json` | open & parse the file | `cron.jobs.use_cron_store()` + `list_jobs()` | survives format changes, auto-repair, locking |
| `executions.db` | open SQLite | `cron.executions.list_executions()` | same query the native `hermes cron runs` uses; no schema coupling |
| `usage_audit.jsonl` | read the file | **read the file — read-only, streaming, one approved exception** | no read API exists in Hermes (writer only, `cron/scheduler.py`); you approved this after I asked |
| `deliveries.db` | join it | **not used** — we take `executions.delivery_outcome` from `list_executions()` | the per-run outcome already lives on the execution row; plan said "deliveries.db only if needed" → not needed |
| writes | — | only `hermes -p <profile> cron pause\|resume\|remove …` subprocess | no code path of ours ever writes a Hermes store |

**Discovery vs. shipped code:** during investigation I did run read-only probes
(`file:...?mode=ro` on `executions.db`, tailing `usage_audit.jsonl`) to disprove the
report's `fire_id` join and to learn field names. **None of that is in the plugin** —
the shipped code in `plugin/` calls only the APIs in §B, with the single
`usage_audit.jsonl` read-only pass as the documented exception (`metrics.py` docstring).
