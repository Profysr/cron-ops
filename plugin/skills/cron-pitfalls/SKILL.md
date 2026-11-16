---
name: cron-pitfalls
description: "Pitfalls and fixes for failing or misbehaving cron jobs."
version: 1.0.0
author: Human Author, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cron, troubleshooting, anti-patterns, security, reliability]
---

# Cron Pitfalls

What not to do, and how to fix cron jobs that misbehave. Avoid monolithic
jobs, hardcoded secrets, and overly aggressive schedules; work the
troubleshooting table for failures.

## When to Use

- A cron job fails, misfires, floods, or behaves unexpectedly.
- Pre-flight review of an existing job before it goes to production.

Does not own: creation/editing/verification procedure — see
`cron-job-creation`; schedule/flag/frequency recommendations — see
`cron-job-standards`; chat output formatting — see `cron-output-formatting`.

## Anti-Patterns

| Anti-Pattern | Problem | Correct Approach |
| --- | --- | --- |
| Vague prompt | Agent must guess intent | Write explicit steps |
| Missing delivery target | Output may go somewhere unexpected | Always specify `--deliver` |
| Missing skill | Agent lacks required domain context | Attach the relevant skill |
| Unpinned production model | Behavior may change | Pin model/provider |
| Unnecessary continuity | Previous output can distort behavior | Use only for stateful jobs |
| Hardcoded secrets | Credentials may leak | Use configured credentials |
| Excessive frequency | Cost/rate-limit/noise problems | Use the lowest useful frequency |
| Monolithic job | Difficult to debug | Split unrelated tasks |
| No empty-result behavior | Agent may produce confusing output | Define `None`/suppression behavior |
| No verification | Broken jobs remain unnoticed | Run and inspect after creation |
| Ambiguous timezone | Wrong execution time | Explicitly establish timezone |
| Invented flags | Command may fail | Use only supported Hermes CLI options |
| Hardcoded fleet inventory in prompt (profile/agent lists) | New fleet members are silently unmonitored; counts go stale | Discover fleet state at runtime — e.g. parse the live `hermes profile list` table and count N/N from actual output |
| Assuming previous conversation context | Cron runs independently | Put required context in the prompt |

## Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `timeout` | Prompt/tool workflow too complex | Simplify or decompose |
| `401/403` | Credential problem | Verify configured credentials |
| Empty output | Query/filter mismatch | Inspect source and filters |
| Duplicate alerts | Missing or ineffective state handling | Add continuity/dedup logic |
| Wrong timezone | Schedule interpreted differently than expected | Verify Hermes/server timezone |
| Model behavior changed | Model/provider changed | Pin production configuration |
| Job not visible | Creation/registration issue | Check `hermes cron list` |
| Run fails immediately | Invalid configuration/prompt/skill | Inspect run output and CLI errors |
| Correct execution but no delivery | Delivery configuration problem | Verify `--deliver` target |
| Correct execution but user says they got nothing | Deliver target is a channel the user isn't watching (e.g. digests pinned to #cron_updates while the user talks in a thread). Compare `Deliver:` in `cron list` against the chat the user is actually in; retarget with `hermes -p <profile> cron edit <id> --deliver discord:<chat_id>` and verify by reading the next run's output file |
| Job "not found" on edit/run/status | Bare `hermes cron <verb>` resolves against the DEFAULT profile; the job may live on another profile. Always use `hermes -p <profile> cron <verb>` for non-default-profile jobs (created jobs report which profile created them; when unsure, list the profile that owns it) |
| Verification run ends `unknown` (owner exited before durable terminal state) | Terminal timeout killed `cron run` mid-execution | Retry with a timeout beyond the job's internal cap, or run it in the background |
| Repeated stale information | Prompt/query does not establish freshness | Define time window explicitly |
| Job workdir/deployed tree vanished mid-day | Shared-memory hub hygiene can delete or move untracked dirs; only git-tracked files are recoverable via `git checkout --` | Commit deployed code trees to the hub repo after deploying; keep secrets/venv gitignored and re-rsyncable from a source package |

Timezone edit procedure and verification steps: `cron-job-creation`.

## Security Rules

Never place secrets directly inside a cron prompt. Never include:

- API keys
- Access tokens
- Passwords
- Session cookies
- Private keys
- OAuth credentials
- Personal authentication material

Prefer configured credentials, environment variables, secret stores, or
Hermes-supported credential mechanisms. Cron prompts may be persisted and
inspected later, so treat them as non-secret configuration.

## Job Scope

A cron job should have one coherent responsibility.

Good:

```
hourly-job-lead-scout
daily-notion-standup
weekly-github-review
```

Avoid one job that:

1. Checks email
2. Searches GitHub
3. Updates Notion
4. Researches competitors
5. Sends a news digest
6. Performs system cleanup

Decompose unrelated responsibilities into separate jobs. This improves
debugging, reliability, cost control, observability, failure isolation, and
prompt maintenance.

## Verification

- Every anti-pattern row was checked against the job under review.
- The troubleshooting row matching the observed symptom was applied, and the
  fix was confirmed by re-running the job (`hermes cron run <job-id>`).
