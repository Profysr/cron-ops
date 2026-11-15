# Feasibility Report — Hermes Cron Operations Extension

**Verdict: FEASIBLE**

Every requested capability maps onto existing Hermes surfaces. Estimated effort: **3–5 days of engineering for a working v1**. No new dependencies are required beyond the Python standard library.

---

## 1. Verified Hermes Architecture

The following architecture was verified on the current host.

### Storage

Cron data is stored under `$HERMES_HOME/cron/` and `$HERMES_HOME/profiles/<profile>/cron/`.

| Component | Purpose and available data |
|---|---|
| `jobs.json` | Job store. Contains a `jobs` dictionary. Each job includes its ID, name, schedule (cron expression or interval), model/provider, delivery target, skills, `no_agent` flag, and prompt. |
| `executions.db` | SQLite database containing durable execution records: ID, job ID, source, PID, status (`claimed`, `running`, `completed`, `failed`, `unknown`), claim/start/finish timestamps, error, delivery outcome, scheduled instant, and progress timestamp. |
| `usage_audit.jsonl` | One record per LLM execution, including prompt tokens, completion tokens, total tokens, model, duration, error, and delivery target. |
| `deliveries.db` | Stores delivery outcomes for executions. |
| `cron_incidents` | Tracks failure signatures, acknowledgement state, and output files. |
| `catch_up_occurrences` | Stores scheduler catch-up state. |
| `ticker_heartbeat` | Stores scheduler heartbeat state. |

The previous audit parsed **305 usage records** across the default and profile stores.

### Hermes CLI

The following commands were confirmed:

```bash
hermes cron list
hermes cron create
hermes cron edit
hermes cron pause
hermes cron resume
hermes cron run
hermes cron remove
hermes cron status
hermes cron runs
hermes cron history
hermes cron incidents
hermes cron notepad
hermes cron doctor
hermes cron tick
```

`hermes cron runs --limit` supports limits from 1 to 500. Cron jobs are profile-scoped; `-p <profile>` selects a profile.

### Plugin system

The plugin system was confirmed through `hermes plugins --help` and official documentation.

A plugin can be installed under:

```text
~/.hermes/plugins/<plugin-name>/
```

Expected components include:

```text
plugin.yaml
__init__.py
schemas.py
tools.py
```

Relevant supported APIs:

- `register(ctx)` — plugin registration entry point.
- `ctx.register_cli_command()` — registers a Hermes CLI subcommand.
- `ctx.register_skill()` — bundles a skill with the plugin.
- `plugin_data_dir()` / `plugin_db()` — sanctioned plugin storage locations.

Validation commands:

```bash
hermes plugins validate --install-deps
hermes plugins doctor validate
```

Plugin catalog admission requires use of public surfaces and prohibits core patching.

---

## 2. Metrics Availability

| Metric | Available? | Source / notes |
|---|---|---|
| Execution duration | Yes | `executions.db` start/finish timestamps; also `usage_audit.jsonl` duration. |
| Token usage | Yes, for LLM runs | `usage_audit.jsonl`. |
| Actual model used | Yes | `usage_audit.jsonl`. |
| Success/failure and error | Yes | `executions.db` status/error and `cron_incidents`. |
| Last 10 runs per job | Yes, derivable | Query the existing stores for the latest 10 records per job. |
| Complexity estimate | Yes, derivable | Deterministic classification based on tokens and duration; no LLM required. |
| CPU/RAM impact | No | Requires additional instrumentation. |
| Delivery outcome | Yes | `deliveries.db`. |

### CPU/RAM instrumentation gap

CPU and RAM usage are not currently recorded in the existing cron stores. Possible approaches:

1. Poll `/proc/<pid>/stat` and `/proc/<pid>/status` using the PID recorded in `executions.db` while a job is running.
2. Use a gateway hook, if a suitable hook exists.

A lightweight sampler is feasible, but it is the only identified metrics gap.

Sampling limitations:
- Very short, sub-second executions may be missed.
- Metrics may become unavailable after a process exits or its PID is reaped.
- Missing measurements must be reported as `unknown`, not estimated.

### Additional observations

- Failed runs may record zero tokens.
- No-agent script jobs do not appear in `usage_audit.jsonl`, so their resource cost is not represented there.
- CPU/RAM instrumentation could help cover resource usage for no-agent jobs as well.

---

## 3. Capability-by-Capability Feasibility

### 3.1 Centralized inventory — Trivial

Read and normalize `jobs.json` across all 12 profile directories plus the default profile.

Python's standard-library `json` and `sqlite3` modules are sufficient. Alternatively, the extension can invoke `hermes -p <profile> cron list`, although direct file reads are faster and easier to parse.

### 3.2 Schedule validation — Easy

Detect jobs scheduled within a ±45-minute window.

The validator should:
- Expand upcoming occurrences of cron expressions.
- Consider all profiles and their configured timezones.
- Flag conflicts when at least one job is agent-backed.
- Allow no-agent script jobs to overlap where appropriate.
- Recommend the nearest available alternative slot.

Cron expressions can be handled with standard-library logic or a small pure-Python dependency such as `croniter`.

### 3.3 Execution metrics — Easy, except CPU/RAM

Join `executions.db` and `usage_audit.jsonl` using the job and execution identifiers.

Keep the latest 10 execution records per job. CPU/RAM sampling can be deferred to v1.1.

### 3.4 Native Hermes integration — Supported

A Python plugin can register:

- `hermes cronops ...` CLI commands through `ctx.register_cli_command()`.
- An agent-facing skill through `ctx.register_skill()`.
- Plugin-owned SQLite storage through `plugin_db()`.

This allows agents across profiles to use the same extension.

### 3.5 Lightweight implementation — Feasible

The proposed implementation uses Python standard-library modules and SQLite. It requires no separate service or daemon for v1.

An optional lightweight sampler may be introduced later, running only while executions are active.

---

## 4. Limitations and Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Internal `jobs.json` and database schemas may change | Hermes upgrades could break readers | Prefer public APIs where possible; validate schemas at startup and fall back to parsing `hermes cron list`. |
| SQLite concurrency | The gateway owns execution databases | Use short-lived, read-only connections. Never write to Hermes-owned stores. |
| CPU/RAM sampling granularity | Short jobs and reaped PIDs may be missed | Mark unavailable measurements as `unknown`. |
| Cross-profile writes | Direct edits to another profile's job store are unsafe | Perform create/edit/pause/resume/remove through Hermes-native CLI/API operations. |
| Global catch-up behavior | `catch_up_missed: true` is a global setting | Validator can report a warning but should not change the setting. |
| Timezone handling | Naive UTC comparisons can produce false conflicts | Use each profile's configured timezone for schedule calculations. |
| Plugin catalog admission | Public-surface requirements apply | Use supported plugin APIs; do not patch Hermes core. |

**Important design boundary:** The extension should validate schedules and manage jobs through Hermes-native operations. It should not directly write to Hermes cron configuration files or execution databases.

---

## 5. Recommended Architecture

### Plugin structure

```text
~/.hermes/plugins/cron-ops/
├── plugin.yaml
├── __init__.py
├── inventory.py
├── validate.py
├── metrics.py
├── sampler.py                 # v1.1
└── skills/
    └── cron-ops/
        └── SKILL.md
```

| File | Responsibility |
|---|---|
| `plugin.yaml` | Plugin manifest; `capabilities: []`. |
| `__init__.py` | `register(ctx)`, CLI command and skill registration. |
| `inventory.py` | Read, normalize, and list jobs across profiles. |
| `validate.py` | Detect ±45-minute conflicts and recommend alternative slots. |
| `metrics.py` | Join execution and usage records; expose the latest 10 runs. |
| `sampler.py` | Optional v1.1 CPU/RAM instrumentation. |
| `SKILL.md` | Explain when and how agents should use the extension. |

### Storage

Use `plugin_db()` for extension-owned SQLite storage.

Suggested tables:
- `metric_cache` — optional derived metrics or rollups.
- `validation_log` — schedule validation results.

Hermes remains the source of truth. Avoid duplicating its primary job and execution records.

### Proposed CLI

```bash
hermes cronops list
hermes cronops validate "0 9 * * *"
hermes cronops metrics <job-id>
```

Additional commands can be introduced for filtering, history, inspection, and supported job management operations.

### Implementation footprint

- Plugin manifest.
- Approximately four core Python modules.
- One bundled skill.
- Approximately 600–900 lines of code.
- No external services.
- No background service required for v1.

---

## 6. Estimated Engineering Effort

| Work item | Estimate |
|---|---:|
| Inventory and metrics | 1 day |
| Schedule validator and recommender | 1–2 days |
| Plugin and skill packaging/validation | 0.5 day |
| CPU/RAM sampler | 1 day (optional, v1.1) |

**Overall estimate:** 3–5 days for a working v1, with CPU/RAM sampling deferred if desired.

---

## 7. Conclusion

The Hermes Cron Operations extension is feasible and low-risk if it uses supported plugin APIs and treats Hermes as the single source of truth.

The recommended v1 should deliver:
- Centralized inventory across profiles.
- ±45-minute schedule conflict detection and recommendations.
- Last-10 execution metrics per job.
- Deterministic complexity classification.
- Native Hermes CLI and bundled skill integration.
- Safe cross-profile management through Hermes-native operations.

Defer CPU/RAM sampling to v1.1. It is the only capability that requires new instrumentation.

**Recommended implementation approach:** Build an independent Hermes plugin, avoid core modifications, keep Hermes-owned stores read-only, and use the plugin's own SQLite database only for extension-specific data.
