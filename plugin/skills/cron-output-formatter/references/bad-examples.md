# Bad Examples — Rejected Cron Outputs

Four rejected reference outputs for `cron-output-formatter`. Each entry
preserves the original text, the defect in it, and (where one exists) the
corrected form. These classify against the raw annotations in
`formatting-patterns.md` (repo root) — where that file labels an example as good but
the final classification rejects it, this file is authoritative.

---

## 1. Gmail Inbox Manager (rejected) — Configuration dump

```text
Cronjob Response: gmail-inbox-manager
(job_id: 81480761c8d1)
-------------

📥 **Gmail Inbox Manager** (2026-11-16 11:00 PKT)
Scanned: 2 | archived: 2 | kept+labeled: 0 | errors: 0

**Categories**
- Banking: 2

**Labels**
EXISTING labels:
- Banking
- Careers
- Finance-Tax
- Jobs
- Newsletters
- Personal
- Receipts
- Security
- Social
- Subscriptions
- Unsorted
NEW labels this run WOULD create:
- (none)

To stop or manage this job, send me a new message (e.g. "stop reminder gmail-inbox-manager").
```

**Defects**

- Dumps the full existing label inventory — persistent configuration that
  is identical every run (principle 11: no configuration dumps).
- `NEW labels WOULD create: (none)` is an empty section with no content
  (principle 12: no artificial sections).
- Actual actions (2 archived) buried under noise; poor emphasis on what
  happened.

**Corrected form**

```text
📥 Gmail Inbox Manager — 16 Nov, 11:00 PKT

✅ Processed 2 emails
- Banking: 2 archived
- Errors: 0

No new labels required.
```

---

## 2. Tech Trends Collect (rejected) — Noise dump + duplicated error

Cronjob Response: tech-trends-collect
(job_id: 90d6525f7bee)
-------------

disabled: arxiv.cs, chatter.other, github.awesome_lists, github.tracked_repos, hf.trending, hn.front_page, hn.show_hn, npm.downloads, openvsx, pypi.rss, quality_gate.osv, reddit.rss, vendor.rss, vscode.marketplace
📡 **Tech trends collect** — ❌ **1 failed** · ✅ 8 ok · ⏸️ 14 disabled

```
✅ github.trending          15 candidates
✅ github.trending_devs     25 candidates
...
❌ github.search_7d         FAILED: BadCredentialsException: 401 {"message": "Bad credentials", "documentation_url": "https://docs.github.com/rest", "status": "401"}
                            unknown coverage, not 'no news'
```

❌ **github.search_7d** — BadCredentialsException: 401 {"message": "Bad credentials", "documentation_url": "https://docs.github.com/rest", "status": "401"}
   Unknown coverage, not 'no news'. Check the token or source.

⚠️ **Run complete:** 35 saved after dedupe -> `2026-11-15-0835.md` | 35 recorded in sources/ | **1 source(s) failed**

To stop or manage this job, send me a new message (e.g. "stop reminder tech-trends-collect").

**Defects**

- Unformatted disabled-sources dump at the top: a raw comma-separated
  name list the reader does not need. Disabled sources are constant
  across runs — report them only when their state changes or they need
  attention; otherwise a count in the headline suffices.
- The `github.search_7d` failure is printed **twice** (inside the status
  block and again below it) — violates principle 4: one event, one
  explanation. "Each and every detail should be conveyed once."
- Section formatting inconsistent (the disabled line misses the
  heading/bullet treatment used elsewhere).

**Fix:** the approved version in `good-examples.md` → Tech Trends
Collect: disabled sources collapsed to `⏸️ 14 disabled` in the headline,
the failure presented once with its plain-language meaning.

---

## 3. Kanban Watch OAuth Batch (rejected) — Narration without structure

```text
Cronjob Response: kanban-watch-oauth-batch
(job_id: 9f5195115c41)
-------------

📋 **Kanban Watch — Google OAuth remediation + Drive design (2 tasks)**

• **OAuth remediation** (t_f05ef9d4)
    Status: BLOCKED — needs human action. Senna finished all remediation work (14:34 comment), but a mis-targeted block call at 14:30 parked this card with a needs_input reason that belongs to the child card t_93d5f14a. The worker asks an operator to complete/unblock-and-reclaim so the record shows done. Deliverable present: `kanban-briefs/comms-oauth-remediation.md` (written 14:26, validation 12/12 pass).

• **Drive design** (t_c8cf5f88)
    Status: RUNNING — in progress for the past ~15 mins (started 14:41, active heartbeats).

Summary: 0 running of note • 0 done • 1 blocked • 0 queued
(0 of 2 tasks finished; batch started 12:32)
Deliverables: comms-oauth-remediation.md ✅ present • drive-integration-design.md ❌ absent

⚠️ Action needed from Bilal: the blocked OAuth card is a false block — the real pending item is child card t_93d5f14a (new product-dedicated OAuth token, needs your presence for browser consent) plus checking consent-screen Publishing status (Testing vs Production) for project idyllic-lotus-513814-m4.

To stop or manage this job, send me a new message (e.g. "stop reminder kanban-watch-oauth-batch").
```

**Defects**

- Excessive technical narration: the blocked-task paragraph retells the
  whole investigation (timestamps, call sequences, validation counts)
  instead of stating status, reason, and deliverable (principle 5:
  human-readable language; principle 8: progressive disclosure).
- Content not humanized and not organized into clear per-task sections —
  status, duration, and deliverables buried in prose.
- Action section unclear: "Action needed from Bilal" mixes the direct ask
  with unrelated technical investigation (consent-screen Publishing
  status, project id), and never states what happens after the action
  (§Action needed rules).

---

## 4. Kanban Overview (rejected) — Unstructured task dump

```text
Cronjob Response: kanban-overview
(job_id: 39a7d26d9e40)
-------------

📋 Kanban overview — 🔴 11 blocked · 🟡 4 todo
1- kanban watcher: one default-profile overview monitor (approved audit architecture)  [senna · blocked] — blocked since 19:27 — Superseded: default profile implements revised spec directly (project kanban-monitoring). Do not retry.
2- Write fleet GitHub identity + repo provisioning policy (hub wiki)  [knowledge · blocked] — blocked since 12:07 — no reason recorded
3- live-flip Discord adapter + mail onboarding (blocked on Bilal credentials)  [default · blocked] — blocked since 22:52 — blocked at creation (human gate / on hold)
4- recovery cards, watchdog tuning, swap measurement, forced-failure run  [code · blocked] — blocked since 16:58 — Paused by user. Defer until gateway stability and resource usage are reviewed.
5- P5: senna SOUL patch — scrapper roster + route line (HUMAN GATE)  [senna · blocked] — blocked since 11:14 — blocked at creation (human gate / on hold)
6- centralized GitHub identity + repo provisioning policy for Hermes fleet  [senna · blocked] — blocked since 12:10 — Paused by user. Stop implementation pending further review.
7- GATE: register a GitHub credential for the fleet (broken push today)  [default · blocked] — blocked since 12:14 — blocked at creation (human gate / on hold)
8- fleet repo provisioner tool (provision.py, stdlib-only, hub project)  [code · blocked] — blocked since 12:16 — no reason recorded
9- Comms-profile Gmail OAuth findings (token perms, stale scopes, docs)  [senna · blocked] — blocked since 14:30 — Needs Bilal's authorization: this *** mints a new OAuth token (new grant) for gmail-inbox-manager and needs him present for the browser consent step. Also the O
10- Google Drive integration for Hermes (drive.file-first) — design only, no implementation  [senna · blocked] — blocked since 16:47 — Paused by user. Stop work pending gateway diagnostics and recovery. (1/2)
```

**Defects**

- A wall of numbered single-line entries — each line packs title, profile,
  state, duration, and full reasoning inline (violates: avoid excessively
  long single-line entries).
- No sections, no prioritization: human-gated work, user pauses, and
  superseded items all look identical (`blocked`).
- Excessive per-task descriptions; truncated mid-sentence at `(1/2)` with
  no clear continuation.
- Confusing blocker states: "Superseded", "human gate", "Paused by user",
  and "no reason recorded" are all rendered as blocked.

**Fix:** group by operational status with human actions first, one-line
reasons per task — see `good-examples.md` → Kanban monitoring (approved).
