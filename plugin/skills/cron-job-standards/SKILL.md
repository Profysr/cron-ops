---
name: cron-job-standards
description: "Recommendations for cron schedules, flags, and frequency."
version: 1.0.0
author: Human Author, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cron, scheduling, recommendations, frequency, reliability]
---

# Cron Job Standards

Advisory standards for designing and tuning Hermes cron jobs: which schedule,
which flags, how often. Recommendations — the mandatory create/verify procedure
lives in `cron-job-creation`.

## When to Use

- Choosing a schedule, flags, or frequency for a new job.
- Tuning an existing job's cadence or configuration.

Does not own: creation/editing/verification procedure or timezone rules — see
`cron-job-creation`. Debugging and anti-patterns — see `cron-pitfalls`.

## Schedule Standard

Prefer explicit cron expressions for production jobs:

| Schedule | Meaning |
| --- | --- |
| `0 8 * * *` | 08:00 every day |
| `0 18 * * 0` | 18:00 every Sunday |
| `0 * * * *` | Every hour |
| `0 */6 * * *` | Every 6 hours |
| `0 3 * * 0` | 03:00 every Sunday |

Human-readable schedules may be used when supported and when they improve
clarity:

```
every 6h
every 30m
daily at 09:00
```

### Production rule

- Use cron expressions when exact execution time matters.
- Use human-readable intervals primarily for simple recurring jobs or
  experimentation.

Timezone interpretation and schedule-editing procedure: `cron-job-creation`.

## Continuity Standard

Use `--continuity` when the task benefits from knowing what happened during the
previous run.

Use continuity for:

- Incremental research
- Scouts/monitors
- News digests
- Deduplication
- Alerting
- "What's new since last run" jobs
- Stateful workflows

Usually do not use continuity for:

- Independent daily briefings
- Stateless health checks
- Simple reminders
- Jobs where previous output could bias the current run

Do not enable continuity merely because it is available.

## Model & Provider Standard

Production cron jobs should be reproducible. Prefer:

```
--model <model> \
--provider <provider> \
--pin
```

or the appropriate Hermes-supported pinning mechanism.

Use model pinning when:

- Output consistency matters.
- The job is business-critical.
- The prompt depends on specific model behavior.
- Cost/performance characteristics must remain predictable.
- The job is expected to run unattended for a long period.

For experiments, model pinning may be omitted intentionally. Never invent model
or provider identifiers — use values supported by the installed Hermes
environment.

## Skill Selection

Attach a relevant skill whenever the job depends on domain-specific
capabilities:

```
--skill notion
--skill github
--skill research
```

Use the actual skill names available in the Hermes installation. If a task
depends on a specialized tool, API, workflow, or domain procedure and an
appropriate skill exists, load that skill.

## Delivery Standard

Always specify the delivery destination. For output intended for the current
conversation:

```
--deliver origin
```

Other destinations may be used when explicitly supported and appropriate:

```
local
discord
telegram
```

Never rely on an implicit default when creating a production job.

## Frequency Guidelines

Avoid unnecessarily aggressive schedules:

| Job Type | Suggested Frequency |
| --- | --- |
| Daily briefing | Daily |
| Weekly review | Weekly |
| Scout/monitor | Hourly |
| Incremental digest | Every 6 hours |
| Health check | Every 15 minutes |
| Cleanup | Daily or weekly |
| API-backed polling | Prefer 15m+ unless faster polling is justified |

Before using a schedule such as `every 5m`, consider:

- API rate limits
- Cost
- Duplicate notifications
- Tool latency
- Whether the information actually changes that frequently

## Job Categories

### Daily Briefing

```
Schedule: daily
Skill: domain-specific
Continuity: usually no
Model pin: yes for production
```

### Weekly Review

```
Schedule: weekly
Skill: domain-specific
Continuity: usually no
Model pin: yes for production
```

### Scout / Monitor

```
Schedule: hourly or slower
Skill: research/web/domain-specific
Continuity: yes
Model pin: yes
```

### Health Check

```
Schedule: every 15m or as required
Skill: none unless required
Continuity: no
Model pin: usually no
```

Prefer `--no-agent` when the check is deterministic and does not require agent
reasoning.

### Incremental Digest

```
Schedule: every 6h
Skill: research/domain-specific
Continuity: yes
Model pin: yes
```

### Cleanup / Maintenance

```
Schedule: off-peak, usually daily or weekly
Skill: devops/system-specific
Continuity: usually no
Model pin: yes for production
```

## Verification

Before finalizing a design, confirm each recommendation was decided
deliberately:

- [ ] Schedule is explicit (or the human-readable form was a conscious choice).
- [ ] Delivery destination is explicit — no implicit default.
- [ ] Frequency is the lowest useful one (rate limits and cost considered).
- [ ] Continuity and model-pin decisions are made for the right reasons,
      not by default.
