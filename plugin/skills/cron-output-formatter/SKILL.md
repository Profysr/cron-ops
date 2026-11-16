---
name: cron-output-formatter
description: "Design and format user-facing cronjob responses for chat delivery."
version: 1.0.0
author: Human Author, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cron, formatting, output, chat, delivery, reporting]
---

# Cron Output Formatter

Design standard for every user-facing cronjob response across the fleet:
information clarity, human readability, operational visibility, relevance,
and consistent presentation.

This is an **output-design skill**, not a cron execution or monitoring
skill. Never change job execution, source collection, task states, or any
underlying operational behavior — only how the result is reported.

## When to Use

- Composing any user-facing cronjob response (Discord/Slack/Telegram/origin).
- Formatting `hermes cron list` / `hermes cron run` results for a human.
- Reviewing or upgrading an existing cron job's output format.

Does not own: creating, editing, or verifying jobs — `cron-job-creation`;
anti-patterns and troubleshooting — `cron-pitfalls`; schedule/flag/frequency
advice — `cron-job-standards`; cross-profile health — `cron-ops`.

## Universal Principles

1. **Signal over noise** — include information because it matters, not merely because the agent collected it.
2. **Outcome first** — start with the most important result, status, or finding.
3. **Summary before details** — the overall situation must be understandable immediately.
4. **One event, one explanation** — never repeat the same error, exception, or finding in multiple sections.
5. **Human-readable language** — translate technical activity into understandable operational language without sacrificing accuracy.
6. **Meaningful hierarchy** — organize with relevant headings, concise bullets, indentation, bold text, code formatting, and restrained emoji.
7. **Actionability** — explicitly identify what requires human intervention and what needs to happen next.
8. **Progressive disclosure** — keep routine output concise; expose deeper diagnostics only when useful.
9. **Status accuracy** — distinguish running, completed, failed, blocked, paused, waiting for approval, superseded, and disabled.
10. **Adaptive length** — match the report's length and complexity to the actual work.
11. **No configuration dumps** — don't repeatedly list unchanged settings, labels, disabled sources, or other persistent configuration.
12. **No artificial sections** — don't add headings that have no meaningful content; omit empty sections.
13. **Evidence-based reporting** — never invent success, progress, timestamps, metrics, or explanations.

## Presentation Levels

Select the level automatically from the work's shape. Do not force every
report into the same template.

### Compact

For simple operations: backups, successful small tasks, simple
notifications, approval reminders.

- Outcome, essential metrics, and relevant warnings only.
- No sections unless the content is real.
- See `references/good-examples.md` → Hermes Backup Snapshot, GitHub Repo
  Request Watcher.

### Structured

For operations with several results: gmail management, research
collection, community digests, routine maintenance.

- Meaningful sections with bold headers (add counts where useful),
  concise summaries, omit empty sections.
- See `references/good-examples.md` → Manage Shared Workspace (Morning),
  Tech Trends Collect (approved).

### Detailed

For complex operations: fleet audits, kanban monitoring, infrastructure
diagnostics, multi-agent workflows, complex maintenance and validation.

- Overview first (aggregate statistics), prioritized findings (attention
  first), relevant grouped details, then actions.
- See `references/good-examples.md` → Cron Fleet Audit, Kanban monitoring
  (approved).

Rule of thumb: 1–3 outcomes → Compact; one domain with multiple results →
Structured; many entities/statuses or mixed domains → Detailed.

## Domain-Specific Rules

### Maintenance

Prioritize health checks, drift, changes, commits, warnings, and important
notes.

### Fleet audits

Start with aggregate job/profile statistics. Surface failures and paused
jobs first. Group the remaining jobs by profile. Avoid unnecessary
configuration information.

### Research and collection

Show source coverage, successful collections, failures, candidate counts,
and saved results. Report disabled sources only when their state changes
or they require attention. Never report failed source coverage as zero
news.

### Kanban monitoring

Organize tasks by meaningful operational status. Distinguish genuine
blockers from false blockers, user pauses, human gates, and superseded
work. Show running duration when useful. Explain dependencies and
deliverables without reproducing entire task descriptions.

### Inbox management

Report emails processed, categorized outcomes, actual archive/label
actions, and errors. Never dump all existing labels on every run. Clearly
distinguish executed actions from dry-run proposals.

### Backups

Prioritize success/failure, filename, compressed size, and execution
duration. Avoid unnecessary sections.

### Approval watchers

Clearly show what requires approval, the requesting profile, project
details, and the consequences of approval. Separate authorization
requirements from technical prerequisites.

## Action Needed

When human intervention is necessary:

- Use a clearly identifiable heading such as `Action needed`.
- State the exact action, explain briefly why it is necessary, identify
  the affected task or resource, and state what happens after the action.
- Keep instructions direct and concise. Never mix unrelated technical
  investigation into the action instructions.
- If no human action is required, omit the section entirely.

## Formatting Standards

- Use a consistent heading hierarchy.
- Use bold for important names, statuses, and key findings.
- Use bullets for individual findings; numbered lists only when order or
  priority matters.
- Use code formatting for IDs, paths, commands, filenames, and exception
  identifiers.
- Use emoji as status indicators, not decoration.
- Use tables only when they improve comparisons.
- Avoid excessively long single-line entries.
- Avoid raw logs unless they are essential to understanding a failure.
- Avoid repeating aggregate counts in multiple places.

## Quality Check (silent)

Before returning any cron response, run this checklist silently and revise
if needed. **Never include this checklist in the actual cron output.**

1. Is the main outcome immediately understandable?
2. Is every included detail relevant?
3. Is the information organized logically?
4. Are any errors or findings repeated?
5. Are statuses represented accurately?
6. Is human intervention clearly explained?
7. Are technical details understandable?
8. Is the report unnecessarily long?
9. Is any important failure or uncertainty hidden?
10. Does the formatting suit the job's complexity?

## References

- `references/good-examples.md` — approved outputs and why they work.
- `references/bad-examples.md` — rejected outputs and the specific defect
  in each.

Read the reference examples before designing a new report shape. Preserve
the lessons and distinctions in these examples — do not merely store the
names.

## Verification

- The main outcome is the first thing the reader sees.
- Every included detail earns its place: no configuration dumps, no
  repeated findings, no empty or artificial sections.
- Statuses match the source output; timestamps and metrics come from the
  source output, never re-derived or invented.
- An `Action needed` section appears only when a human must act, and is
  direct and concise when present.
- The silent quality check passed before delivery.
