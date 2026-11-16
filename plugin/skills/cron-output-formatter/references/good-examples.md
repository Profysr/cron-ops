# Good Examples — Approved Cron Outputs

Seven approved reference outputs for `cron-output-formatter`. Each entry
preserves the original text plus the lessons it demonstrates. Use these to
calibrate new report shapes; preserve the lessons, not just the names.

---

## 1. Manage Shared Workspace (Morning) — Structured maintenance

```text
Cronjob Response: Manage Shared Workspace (Morning)
(job_id: maint-morning)
-------------

Hub maintenance — 2026-11-16 UTC

**Needs review** (5)
- inbox/vault/librarian-lint.md — dry run found 0 claims with provenance
- inbox/vault/librarian-profile-spec.md — dry run found 0 claims with provenance
- inbox/vault/priority-task-list.md — dry run found 0 claims with provenance
- inbox/vault/scout-findings.md — dry run found 0 claims with provenance
- inbox/vault/trend-finder-findings.md — dry run found 0 claims with provenance

**Doctor**
- ✅ PASS 18/18

**Facts**
- No drift. The ledger holds 12 facts in both facts.md and facts.db.
- No rebuild was needed.

**Commits** (1)
- 1d39f5a — committed concurrent workspace output, the brain health digest, and a .gitignore entry for the nested cron-ops repo

**Notes**
- The monitor diff showed the inbox/vault count drop from 8 to 5. A prior cycle deleted the 3 marker-bearing reports. The claims were already on live wiki pages.
- No file under inbox/, knowledge-base/, or sources/ was newer than the last commit. The current monitor digest matches the stored snapshot. The wake was a duplicate.
- The gate found no new inbox report under inbox/tech-runs/. That directory does not exist this cycle.
- I staged no new source. The only untracked file under sources/ was a scrapper artifact envelope. It is placed output, not captured evidence.
- I added workspace/projects/cron-ops/ to .gitignore. That project owns its own .git history. Git was staging it as an embedded repository.

To stop or manage this job, send me a new message (e.g. "stop reminder Manage Shared Workspace (Morning)").
```

**Why it works**

- Outcome first: date line, then items needing review, then health.
- Meaningful sections with counts in headers (`**Needs review** (5)`,
  `**Commits** (1)`); no empty sections.
- Health check compressed to one line (`✅ PASS 18/18`), not a dump.
- Notes are human-readable operational prose — what changed, why, and what
  the agent did about it — not raw tool output.

---

## 2. Cron Fleet Audit — Detailed, attention-first

```text
Cronjob Response: cron-fleet-audit
(job_id: 1bc8532899db)
-------------

**⏰ Cron Fleet Audit** — 16 Nov 08:02 PKT
19 jobs / 11 profiles · ✅ 17 ok · ⏸ 1 paused · ❌ 1 failed

**🚨 Attention**
• **social-gmail-triage-digest** — `comms` — paused
• **tech-trends-collect** — `research` — failed 16-05:31 — why: Script exited with code 1

**default** (8)
• ✅ Manage Shared Workspace (Morning) — next 16-09:00 · last 15-09:05
• ✅ Manage Shared Workspace (Evening) — next 16-22:30 · last 15-22:35
• ✅ cron-fleet-audit — next 17-08:00 · last 15-08:04
• ✅ community-updates-digest — next 16-13:00 · last 16-01:01
• ✅ hermes-backup-snapshot — next 17-00:05 · last 16-00:09
• ✅ key-rotation-reminder — next 12-09:00 · last 12-09:06
• ✅ gmail-testing-mode-reminder — next 20-11:24 · last None
• ✅ kanban-overview — next 16-08:35 · last 16-07:50

**comms** (2)
• ⏸ social-gmail-triage-digest — next 08-18:00 · last 08-04:06
• ✅ gmail-inbox-manager — next 16-09:00 · last 16-08:01

**research** (2)
• ❌ tech-trends-collect — next 16-13:30 · last 16-05:31
• ✅ Daily Trend Updates — next 16-13:30 · last 16-01:32

**senna** (7)
• ✅ daily-briefing — next 16-13:00 · last 15-13:31
• ✅ books_reading — next 16-14:30 · last 16-02:37
• ✅ books_reading_sunday_review — next 22-02:30 · last 15-02:34
• ✅ memory-reminder — next 23-07:00 · last 16-07:13
• ✅ review-day-reminder-morning — next 16-09:00 · last 15-09:03
• ✅ review-day-reminder-evening — next 16-20:30 · last 15-20:30
• ✅ soul-auditor — next 22-08:00 · last 15-08:12

_Empty (7): career, code, designer, finance, knowledge, worker-a, worker-b_

Total: **19** jobs across 11 profiles

To stop or manage this job, send me a new message (e.g. "stop reminder cron-fleet-audit").
```

**Why it works**

- Aggregate statistics first: `19 jobs / 11 profiles · ✅ 17 ok · ⏸ 1
  paused · ❌ 1 failed` — the whole situation in one line.
- `**🚨 Attention**` before everything else; only failures and pauses
  appear there, each with its cause.
- Remaining jobs grouped by profile with counts in headers; empty profiles
  collapsed to a single line instead of seven empty sections.
- Dense but scannable: compact `next/last` timestamps, status emoji as
  indicators, no configuration dumps.
- Total line closes the loop without repeating the rollup counts.

---

## 3. Community Updates Digest — Structured discovery list

```text
Cronjob Response: community-updates-digest
(job_id: 7fb77edcc9fd)
-------------

🆕 **10 new entries** — latest contributions
🔗 2 integrations · 🔧 6 tools · 🔌 1 plugin · 🧩 1 skill

---

1. Mibly Apple Health Mcp — integration (productivity)
2. Hermes Agent Android Phone Only — tool (devops)
3. Hermes Desktop Light — tool (ui)
4. prebuilt Hermes Desktop Light for Linux (AppImage + .deb) — tool (ui)
5. Hermes Kernelbench — tool (research)
6. KernelBench-Hard × Hermes Agent — tool (research)
7. Wake words for Hermes — tool (voice)
8. Wake words for Hermes — integration (voice)
9. Hermes Plugin Computer Use Plus.Git — plugin (productivity)
10. Hermes Dont Fxxking Change My Skills — skill (security)

---

**1. Mibly Apple Health Mcp** 🔗 — integration/productivity by littlenew
Mibly connects Apple Health data to any personal AI agent through an MCP server, so agents can read workouts, heart rate and other Health records.
🔗 [source](https://github.com/littlenew117/mibly-apple-health-mcp)

**2. Hermes Agent Android Phone Only** 🔧 — tool/devops by Vendedor
Guide and configs for running Hermes fully phone-only on a Galaxy S24 Ultra via Termux (Android 16): CLI plus dashboard, no desktop involved.
🔗 [source](https://github.com/Padilha-BR/hermes-agent-android-phone-only)

**3. Hermes Desktop Light** 🔧 — tool/ui by Diego
hermes-desktop-light: a lightweight community build of Hermes Desktop for Linux, distributed as prebuilt AppImage and .deb packages.
🔗 [source](https://github.com/dacog/hermes-desktop-light)

**4. prebuilt Hermes Desktop Light for Linux (AppImage + .deb)** 🔧 — tool/ui by Diego
Prebuilt hermes-desktop-light for Linux: AppImage and .deb packages of the lightweight hermes-desktop-light build.
🔗 [source](https://dacog.github.io/hermes-desktop-light)

**5. Hermes Kernelbench** 🔧 — tool/research by TanmayPatil (1/2)
```

**Why it works**

- Summary before details: headline count plus a breakdown by type, then
  the compact numbered index, then per-item detail with source links.
- Each detail appears exactly once (index line, then one detail block).
- One-line human explanation per entry — no raw repository metadata.
- `(1/2)` pagination marker for long digests instead of an unbounded wall.

---

## 4. Tech Trends Collect (approved) — Collection with one failed source

Cronjob Response: tech-trends-collect
(job_id: 90d6525f7bee)
-------------

📡 **Tech trends collect** — ❌ **1 failed** · ✅ 8 ok · ⏸️ 14 disabled

```
✅ github.trending          15 candidates
✅ github.trending_devs     25 candidates
✅ yc.launches              15 candidates
✅ producthunt.posts        10 candidates
⚪ officialskills.snapshot  0 candidates
✅ skillsh.installs         21 candidates
✅ skillsh.trending_hot     30 candidates
✅ trendshift.repos         6 candidates
❌ github.search_7d         FAILED: BadCredentialsException: 401 {"message": "Bad credentials", "documentation_url": "https://docs.github.com/rest", "status": "401"}
                            unknown coverage, not 'no news'
```

⚠️ **Run complete:** 35 saved after dedupe -> `2026-11-15-0835.md` | 35 recorded in sources/ | **1 source(s) failed**

To stop or manage this job, send me a new message (e.g. "stop reminder tech-trends-collect").

**Why it works**

- Headline rollup first: failed/ok/disabled counts in one line.
- Aligned, compact per-source status block — one line per source, counts
  visible at a glance.
- The failure appears **once**, with the raw exception and a plain-language
  meaning attached (`unknown coverage, not 'no news'`) — never reported as
  zero results.
- Disabled sources are a count in the headline, not a name dump.
- Saved-results summary closes with what was produced and how many
  sources failed.

---

## 5. Kanban monitoring (approved) — Status-grouped tasks

```text
Cronjob Response: kanban-overview
(job_id: 39a7d26d9e40)
-------------

📋 Kanban overview — 15 pending tasks

**🚨 Needs your attention (2)**
- Gmail OAuth — Browser consent required.
- GitHub credentials — Registration required.

**⏸ Paused (2)**
- Recovery cards — Waiting for gateway diagnostics.
- GitHub provisioning — Implementation paused by user.

**🔒 Blocked (remaining tasks)**
- Fleet GitHub identity policy — No blocker reason recorded.
- Fleet repo provisioner — Waiting for dependency resolution.

**♻️ Superseded (1)**
- Kanban watcher — Replaced by the revised monitoring project.
  No retry required.

**Summary**
2 human actions · 2 paused · 1 superseded · ...
```

**Why it works**

- Organized by meaningful operational status, with human actions first.
- Distinguishes genuine blockers from user pauses, human gates, and
  superseded work — each with a one-line reason.
- Short entries instead of wall-of-text task descriptions; the summary
  closes with aggregate counts.
- This is the corrected form of the rejected unstructured kanban dump in
  `bad-examples.md`.

---

## 6. Hermes Backup Snapshot — Compact

```text
Cronjob Response: hermes-backup-snapshot
(job_id: fbe4d1b7e78c)
-------------

✅ Backup created successfully
📦 Filename: hermes-backup-20261116-000554.zip
💾 Compressed size: 217M
⏱️ Time taken: 3m 15s

To stop or manage this job, send me a new message (e.g. "stop reminder hermes-backup-snapshot").
```

**Why it works**

- Pure outcome: success, filename, size, duration. Nothing else.
- Emoji as status indicators/metric labels, not decoration.
- Adaptive length: the work was simple, so the report is four lines.

---

## 7. GitHub Repo Request Watcher — Compact, decision-oriented

```text
Cronjob Response: github-repo-request-watcher
(job_id: d3896b3e00b9)
-------------

**Pending GitHub repository request digest** — 1 request (unchanged from last run, still awaiting approval):

- **Project:** policy-test-project
- **Requesting profile:** default
- **Description:** Temporary validation project for GitHub policy
- **Local path:** `/home/ubuntu/.hermes/cache/scratch/github-policy-test/proj`
- **Visibility:** private
- **GitHub owner:** Profysr
- **Initial commit message:** "initial commit: policy validation project"
- **Commit count:** 1
- **Request id:** `20261115T072615Z-policy-test-project`

**Reminder:** Your approval is required before any remote is created or anything is pushed. Provisioning runs `approve-repo.sh` only after you approve. Also note the h-senna App key is still **missing** at `~/.hermes/secrets/h-senna.pem` — provisioning cannot work until it is installed.

To stop or manage this job, send me a new message (e.g. "stop reminder github-repo-request-watcher").
```

**Why it works**

- Decision-oriented: what is pending, unchanged-from-last-run called out
  so the reader knows nothing new happened.
- Approval requirement (authorization) kept separate from the missing
  App key (technical prerequisite).
- Bold labels make the field list scannable; IDs and paths in code
  formatting.
- The reminder states the action, why, and what blocks provisioning —
  direct, no unrelated investigation mixed in.
