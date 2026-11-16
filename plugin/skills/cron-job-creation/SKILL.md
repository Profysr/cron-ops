---
name: cron-job-creation
description: "Create, edit, and verify Hermes cron jobs end-to-end."
version: 1.0.0
author: Human Author, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cron, scheduling, creation, verification, reliability, hermes]
---

# Cron Job Creation

Standard operating procedure for creating reliable, observable, maintainable,
production-ready scheduled jobs in Hermes Agent. This skill is authoritative
for Hermes cron-job creation: follow it unless the user explicitly requests an
exception. Do not treat a cron command as complete merely because
`hermes cron create` succeeds.

## When to Use

- Creating, editing the schedule of, or verifying a Hermes cron job.
- Deciding whether a task belongs in cron at all.

Does not own: schedule/flag/frequency recommendations — see
`cron-job-standards`; anti-patterns and troubleshooting — see `cron-pitfalls`;
cross-profile inventory and conflict validation — see `cron-ops`.

## Core Rule

A Hermes cron job must be:

1. **Explicit** — schedule, purpose, inputs, and expected output are unambiguous.
2. **Self-contained** — the prompt contains everything the agent needs to perform the task.
3. **Scoped** — the job performs one coherent responsibility.
4. **Observable** — execution can be inspected and verified.
5. **Reliable** — failures, empty results, duplicates, and timezone issues are handled.
6. **Reproducible** — production jobs should pin their model/provider configuration.
7. **Safe** — secrets must never be embedded directly in prompts.
8. **Verified** — newly created production jobs must be run and inspected before being considered complete.

## Eligibility — Is This Even a Cron Job?

Before writing any job, decide whether the work is cron-shaped or
conversation-shaped. A Hermes cron run is fire → execute → deliver → exit: there
is no input channel into a running execution, it cannot pause, wait, or ask the
user anything mid-run. Human-gated work does not belong in cron.

### Cron-shaped (build it)

- Deterministic, self-contained prompt — everything needed is in the prompt or reachable from tools.
- No human decision between steps; any gating is a rule (thresholds, hashes, diffs), not a judgment call.
- Bounded runtime well under the execution cap; failure, empty-result, and duplicate behavior explicitly defined.
- Output is a deliverable (report, digest, alert) or a side effect that is safe unverified (a draft, a log line, a cache refresh).
- Real recurrence — a person would notice if a cycle were skipped.

### Conversation-shaped (do NOT build it as cron)

- Needs human input mid-run: choosing among options, approving edits, answering questions.
- Approval-gated side effects: the run must not mutate anything until a human signs off. Build a chat-driven skill with durable state instead; cron may only draft or remind.
- Open-ended iteration: work continues until a person judges it done.
- Presence-dependent: the run is useless when the user is unavailable (draft-only wrappers excepted).
- Routinely hits the execution time cap — the job is mis-shaped, not under-tuned.

### Decision checklist (all five must be YES)

1. Can the full task be described with zero questions to the user?
2. If the user never shows up, is the run still safe and useful (draft/report only, no destructive writes)?
3. Can failure, empty, and duplicate outcomes be handled by rules written into the prompt?
4. Does it fit comfortably inside one execution's time budget?
5. Is the cadence real?

Any NO → build it as a chat-driven skill with durable state; keep cron only as
a nudge or drafter.

## Canonical Creation Format

Use this structure for production jobs:

```bash
hermes cron create "<CRON_SCHEDULE>" "<PROMPT>" \
  --name "<kebab-case-name>" \
  --deliver origin \
  --skill <relevant-skill> \
  --model <pinned-model> \
  --provider <provider> \
  --continuity \
  --pin
```

Only include flags that are actually appropriate for the job. Do not invent
skill names, model names, providers, or unsupported flags — use only flags
confirmed to exist in the installed Hermes version. When to choose each flag
(`--continuity`, `--model`/`--pin`, `--skill`, `--deliver`) and which schedule
to pick: see `cron-job-standards`.

## Timezone Rule — Local Wall Clock, No Hardcoded Zones

- Assume cron expressions use the Hermes/server timezone unless Hermes documentation or the current environment explicitly establishes another behavior. **Never assume the user's local timezone is the server timezone.**
- NEVER pin a per-job timezone (`--timezone`) unless the user explicitly asks for a specific zone. Per-job pins are the multi-market exception, not the fleet default.
- A cron expression is read in the profile's timezone (`timezone:` key in the profile's `config.yaml`). Fleet standard: that config resolves to the system local zone, so `0 8 * * *` fires 08:00 local (on a PKT host, 08:00 PKT — "8:30 AM" must mean 8:30 local, never 8:30 UTC).
- When local-time execution is required: (1) determine the intended timezone, (2) determine how Hermes interprets the schedule, (3) convert the schedule when necessary, (4) state the timezone explicitly in the prompt when relevant.
- When a job is created, or the profile has no `timezone:` key, verify resolution: inspect `next_run_at` in the job store (`$HERMES_HOME/cron/jobs.json`, or `$HERMES_HOME/profiles/<profile>/cron/jobs.json`). It must carry the local offset. If it shows a foreign offset, set `timezone: <Zone/Name>` in the profile's `config.yaml` (e.g. `Asia/Karachi`), then re-save each affected job's schedule (`hermes cron edit <id> --schedule "<expr>"`) so `next_run_at` recomputes in the new zone, and read the values back to confirm.
- `hermes cron list` next-run rendering can display in the job's own basis; the dispatch record's `scheduled` field and the stored `next_run_at` are ground truth for when a job fires. Verify against those, not the pretty display.
- A timezone-affecting config change may need a gateway restart to reach the live scheduler — tell the user to restart (`hermes -p default gateway restart`); never restart the gateway autonomously.

## Editing Job Schedules (Mandatory Procedure)

Every time a cron job's timing changes, use `cron edit --schedule` — never
recreate the job or hand-edit job-store files.

### Command

```bash
hermes -p <profile> cron edit <job_name> --schedule "<CRON_EXPRESSION>"
```

- Use `-p <profile>` whenever the job lives in a non-default profile (cron jobs are per-profile).
- The job may be referenced by its human-readable **name** (e.g. `tech-trends-collect`) or its job ID.
- Quote the full cron expression, e.g. `--schedule "30 7,15,23 * * *"`.

### Example

```bash
# Move tech-trends-collect (research profile) to 07:30/15:30/23:30:
hermes -p research cron edit tech-trends-collect --schedule "30 7,15,23 * * *"
```

### Timezone rule for edits

Build the cron expression in the profile's configured timezone (see the
Timezone Rule above). Confirm which offset the schedule is expressed in by
reading the `timezone:` key of the main and profile `config.yaml` files, then
do not apply any extra conversion.

### Mandatory verification after every edit

```
hermes -p <profile> cron list
```

The edit is only complete when `cron list` shows:

- [ ] `Schedule:` reflects the new cron expression.
- [ ] `Next run:` lands on the intended local time **with the expected UTC offset** (e.g. `+05:00` for PKT).

A successful `cron edit` confirmation message alone is **not** verification. If
the displayed offset looks wrong, fall back to ground truth: the stored
`next_run_at` in the profile's `cron/jobs.json`.

## Failure Handling

Cron prompts should explicitly handle expected failure modes.

### API Failure

```
If the source API is unavailable, report the failure clearly and do not fabricate results.
```

### Empty Result

```
If there are no matching items, report "None" rather than inventing items.
```

### Partial Failure

```
If one source fails, report that source as unavailable and continue with the remaining sources when safe.
Do not fabricate data for the unavailable source.
```

### Duplicate Results

Use continuity where appropriate and explicitly instruct the agent what
constitutes a duplicate.

## Verification Is Mandatory

A cron job is only complete when it is registered, run, inspected, and verified
to run on schedule. A successful `hermes cron create` command does **not** mean
the job is production-ready.

### Step 1 — Confirm Registration

```
hermes cron list
```

Verify: job exists, name is correct, schedule is correct, delivery target is
correct, configuration is present. If supported: `hermes cron list | grep <job-name>`.

### Step 2 — Run Immediately

```
hermes cron run <job-id>
```

`cron run` blocks until the execution finishes. Budget the terminal timeout
well past the job's own internal time cap (a job with a 3-minute cap needs
5-10 minutes of wall time) — a shorter timeout kills the run mid-flight and the
scheduler records it as `unknown` ("owner exited before a durable terminal
state"), which fails verification. For a job on another profile:
`hermes -p <profile> cron run <job-id>`.

Verify: execution completes, no errors occur, tools/API calls work, output
follows the requested format, no data was hallucinated, empty-result behavior
works.

### Step 3 — Inspect Runs

```
hermes cron runs <job-id>
```

Verify: status is successful, no timeout occurred, runtime is reasonable,
output is present, errors/warnings are understood.

### Step 4 — Verify Next Run

```
hermes cron list
```

Verify that the next execution matches the intended schedule and timezone.

### Step 5 — Confirm Delivery

For jobs using `--deliver origin`, confirm that the output actually arrives in
the originating conversation.

### Production Rule

Do not report a newly created cron job as **verified** unless the immediate run
and execution result have been checked.

## Quick Reference

### Create

```
hermes cron create "0 8 * * *" "<detailed self-contained prompt>" \
  --name daily-standup \
  --deliver origin \
  --skill notion \
  --pin
```

### Run

```
hermes cron run <job-id>
```

### Inspect Runs

```
hermes cron runs <job-id>
```

### List

```
hermes cron list
```

### Pause

```
hermes cron pause <job-id>
```

### Remove

```
hermes cron remove <job-id>
```

Only use commands/flags confirmed to exist in the installed Hermes version.

## Production Readiness Checklist

Before considering a cron job complete:

- [ ] Job has a descriptive kebab-case name.
- [ ] Schedule is explicit and intentional.
- [ ] Timezone behavior is understood.
- [ ] Prompt is self-contained.
- [ ] Prompt clearly defines the task.
- [ ] Required resources/IDs are included.
- [ ] Relevant skill is attached.
- [ ] Delivery destination is explicit.
- [ ] Continuity is enabled when state is required.
- [ ] Model/provider is pinned when reproducibility matters.
- [ ] No secrets are embedded in the prompt.
- [ ] Empty-result behavior is defined.
- [ ] Failure behavior is defined where relevant.
- [ ] Job is scoped to one coherent responsibility.
- [ ] `hermes cron list` confirms registration.
- [ ] `hermes cron run <job-id>` succeeds.
- [ ] `hermes cron runs <job-id>` shows a successful execution.
- [ ] Output quality has been inspected.
- [ ] Next scheduled run has been verified.
- [ ] Delivery has been confirmed.

## Final Rule

**A cron job is not complete when it is created. It is complete when it is
correctly configured, successfully executed, inspected, and verified to run on
the intended schedule.**

When creating or modifying Hermes cron jobs, follow this skill by default and
prefer reliability, explicitness, observability, and reproducibility over the
shortest possible command.
