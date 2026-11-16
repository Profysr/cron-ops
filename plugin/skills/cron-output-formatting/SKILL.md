---
name: cron-output-formatting
description: "Format cron list and run output for chat delivery."
version: 1.0.0
author: Human Author, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cron, formatting, output, chat, delivery]
---

# Cron Output Formatting

Turn raw `hermes cron list` / `hermes cron run` output into a scannable status
message for chat delivery (Discord/Slack/Telegram/origin).

## When to Use

- The user asks to show cron status, runs, or a job list in chat.
- Reporting the result of `hermes cron list` or `hermes cron run` to a human.

Does not own: creating, editing, or debugging jobs — see `cron-job-creation`
and `cron-pitfalls`.

## Procedure

1. **Capture output** — run the cron command and store its stdout.
2. **Parse sections** — isolate *Name*, *Schedule*, *Last run*, *Execution* fields.
   - If JSON: use `jq` or Python `json.load()`.
   - If plain text: use `grep -E "^(Name|Schedule|Last run|Execution):"`.
3. **Classify items** — based on `Last run` timestamp and task status:
   - **Overdue**: `next run` is in the past and `last run` status is not `ok`.
   - **Pending**: `next run` is in the future.
   - **Completed**: `last run` status is `ok`.
4. **Strip internal syntax** — replace `[[...]]` and `^[...]` with display text only.
5. **Assemble output** — format with emojis and bullet lists:

   ```text
   🔴 Overdue
   - <task name> - path: <raw path>

   🟡 Pending
   - <task name> - next run: <datetime>

   ✅ Completed
   - <task name> - last run: <datetime>
   ```

6. **Send to user** — echo the final string for Discord/Slack/Telegram delivery.

## Pitfalls

- **Always orient first** — read the latest cron output before applying formatting.
- **Do not assume JSON** — Hermes may emit plain text; guard with a conditional branch.
- **Avoid duplicate emojis** — ensure each section header appears once.
- **Handle empty sections** — if no items fall into a category, omit that section entirely.

## Verification

- Every item appears exactly once, under exactly one heading.
- No `[[...]]` / `^[...]` syntax remains in the delivered message.
- Timestamps shown come from the source output, not re-derived values.
