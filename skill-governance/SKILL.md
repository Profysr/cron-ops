---
name: skill-governance
description: Govern creation, modification, and verification of skills.
version: 3.3.0
author: Human Author, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [skills, authoring, governance, maintenance, verification]
    related_skills: [hermes-agent]
---

# Govern Hermes Skills

Authoritative governance and operating procedure for creating, modifying, reviewing, merging, and maintaining Hermes skills. 

The goal is a clean, reliable skill ecosystem with clear ownership, minimal proliferation, explicit boundaries, one canonical implementation per procedure, and verified behavior.

---

## When to Use

Use this skill when:
* Creating a new Hermes skill.
* Modifying, upgrading, or refactoring an existing skill.
* Reviewing a skill for production quality.
* Comparing or consolidating overlapping skills.
* Splitting a skill with multiple unrelated responsibilities.
* Deprecating or replacing a skill.
* Auditing a skill's dependencies or dependents.
* Deciding whether a workflow should become a skill.

> **Do not** create a skill merely because a task is complex. Prefer an existing skill, workflow, tool, script, reference, or extension when it already owns the required responsibility.

---

## Core Principles

### 1. One Responsibility -> One Authority
Every responsibility must have one authoritative skill. Before creating or substantially changing a skill:
1. Discover existing skills.
2. Search for overlapping responsibilities.
3. Read the most relevant skills.
4. Identify the current authority.
5. Define what the proposed skill owns and explicitly **does not** own.

*If an existing skill already owns the responsibility, extend or improve it instead of creating a competing skill.*

### 2. One Procedure -> One Canonical Implementation
Each executable procedure must have one authoritative implementation. Do not duplicate the same logic across skills, scripts, references, templates, or external files. If duplicates exist:
* Identify the authority.
* Move callers to it.
* Remove or deprecate the duplicate.
* Verify the result.

### 4. Use Hermes-Native Tools
Use Hermes-native tools when they provide the required capability. Do not teach skills to reproduce existing Hermes tool capabilities with raw shell commands.

The skill-management tool surface (use these — never raw file edits or shell loops — for skill work):
* `skill_manage` — create, patch, consolidate, and delete skills, including `references/`, `scripts/`, and `templates/` supporting files. All edits are atomic operation batches; targeted `patch` ops are preferred over full-file rewrites.
* `skill_view` — load a skill's full SKILL.md and linked files before acting on it. Re-issue after context compression: a `[SKILL_PRUNED]` placeholder means the content is inaccessible until reloaded.
* `skills_list` — enumerate available skills (optionally filtered by category) when discovering what exists.
* Chat/CLI equivalents: `/skills` (list, search, install in chat), `/learn` (material → skill via `skill_manage`), and `hermes skills list|search|browse|install|inspect|check|update|audit|uninstall` from the terminal.

## Skill Discovery — Where to Find Skills and Templates

Before authoring a new skill, search existing registries — an existing skill may already own the responsibility. Discovery sources, Hermes-integrated:

| Source | Identifier | Notes |
| --- | --- | --- |
| Official optional skills (`official`) | `official/security/1password` | Ships with Hermes; built-in trust. Catalog: docs → Official Optional Skills Catalog. |
| **skills.sh** (`skills-sh`) | `skills-sh/vercel-labs/...` | Vercel's public agent-skills directory at https://skills.sh/ — install-count leaderboard (all-time/trending/hot). Search: `hermes skills search <query> --source skills-sh`. |
| agentskills.io | — | The open skill-specification standard; its hub indexes community skills. |
| Hermes Skills Hub | https://hermes-agent.nousresearch.com/docs/skills | Public catalog snapshot (`/docs/api/skills.json`); same data as Desktop's Browse tab. |
| `well-known` | `well-known:https://site/.well-known/skills/...` | Sites publishing skills directly. |
| `github` / custom taps | `openai/skills/k8s` | Direct repo installs; `hermes skills tap add owner/repo`. |
| `clawhub`, `lobehub`, `browse-sh` | Source-specific | Community marketplaces. |
| Direct URL | `https://.../SKILL.md` | One-off install of a raw SKILL.md. |

Workflow: `hermes skills search <query>` (spans registries) → `hermes skills inspect <id>` → review → `hermes skills install <id>` (security scan runs automatically; `--force` bypasses it — avoid). Community-sourced skills default to trust level `community`; re-scan with `hermes skills audit` after upstream updates. Any third-party skill adopted this way still passes the quality gates below before it is treated as canonical.

Use Hermes' native installer, not external installers: `npx skills add ...` (Vercel) targets Claude Code and similar agents (`~/.claude`, `~/.agents/skills`) and does NOT register the skill in Hermes. `hermes skills install` reads the same skills.sh index and adds the security scan and registration.

Global vs specific placement (decide before installing):
1. Determine scope: will 2+ profiles use this skill (global) or only one (specific)?
2. If global: read `skills.external_dirs` from the profile `config.yaml` to find the shared dir (this fleet: `shared-memory/.skills/`), install with `hermes skills install <id> --yes`, then move the skill folder from the profile-local `skills/` into that external dir — `hermes skills install` has no destination flag, so install-then-move is the standing workflow.
3. If specific: install normally and leave it in the profile-local dir.
4. **If a similar skill exists in both the local dir and the external dir, disable the local one** (profile config `skills` disabled list) so the external/canonical copy is the one that loads — silent shadowing otherwise makes one copy stale.

### 3. Chunked Edits (SOUL.md Core Principle)
Modify existing skills with localized patch operations only — never whole-file read/write rewrites. Read only the sections being changed; apply one patch per section. Wholesale rewrites risk losing unrelated concurrent edits and violate the SOUL.md "Incremental & targeted edits" principle.

### 4. No Machine-Specific Assumptions
Never hard-code user-specific paths such as `/home/user/...`, `/Users/name/...`, or `C:\Users\name\...`. Use repository-relative paths, environment variables, or portable path handling.

### Verification Is Part of the Work

A skill is not complete simply because the file exists, YAML parses, or the agent believes it succeeded. Completion requires appropriate validation and behavioral verification.

### See Also
- `references/skill-comparison-methodology.md` — Skill comparison methodology for categorical-level inspection, emerged from Phase 2 folder reconciliation workflow. *(Note: file not yet present in this skill directory — write it before relying on it.)*

---

## Lifecycle

Use this lifecycle for meaningful creation or modification:

```text
DISCOVER ➔ COMPARE ➔ ESTABLISH AUTHORITY ➔ DEFINE BOUNDARY ➔ 
AUDIT DEPENDENCIES ➔ AUDIT DEPENDENTS ➔ DESIGN ➔ IMPLEMENT ➔ 
VALIDATE and VERIFY ➔ ECOSYSTEM AUDIT ➔ REPORT

```

> Do not skip a stage merely because the requested change appears small. For trivial wording-only changes, reduce verification depth appropriately.

### Phase 1 — Discover

Before creating or substantially modifying a skill, inspect the existing skill ecosystem using Hermes tools to find related skills, repository conventions (`AGENTS.md`), and relevant workflows, scripts, references, templates, and tests.

### Phase 2 — Compare

Compare relevant skills by responsibility, not by name. Determine what each owns, when it applies, and its dependencies. Choose one path:

* Extend an existing authority.
* Split an existing authority.
* Consolidate overlapping authorities.
* Create a new authority *(last option)*.

### Phase 3 — Define the Boundary

Before implementation, clearly define:

* **Owns:** The responsibility this skill controls.
* **Does Not Own:** Adjacent responsibilities handled elsewhere.
* **Dependencies:** What this skill requires.
* **Dependents:** What relies on this skill.
* **Canonical Implementation:** Where its executable logic lives.

### Phase 4 — Decide Skill Placement

* Use `bundled skills/<category>/` for broadly useful, frequently used, lightweight capabilities.
* Use `optional-skills/<category>/` for niche, domain-specific, integration-heavy, or specialized capabilities.
* **Do not** create router/hub skills whose main purpose is directing work to other skills.

#### Local vs external (shared hub) placement — precedence rules

Skills resolve from two layers: the profile-local `skills/` dir and `skills.external_dirs`
(e.g. the shared-memory hub `.skills/`). Rules that keep this from decaying:

* **Local precedence:** on a name collision, the profile-local copy loads; the external copy is
  silently shadowed and goes stale. Never leave a duplicate in both layers — that is the
  primary mis-management hazard.
* **Placement doctrine:** the hub `.skills/` dir is the canonical home for fleet-shared skills
  (one authority, every profile picks it up via `external_dirs`). Profile-local is for
  (a) skills only that profile needs, or (b) a deliberate local override — which must be a
  rename (e.g. `<name>-local`) or a recorded decision, never an accidental duplicate.
* **Where the agent writes:** new skills default to the profile-local dir unless
  `skills.create_dir` is set; `external_dirs` only affects reading/scanning. Hub-installed
  skills intended for all profiles must be moved into the external dir after install
  (`hermes skills install` has no destination flag).
* **Where the agent edits:** `skill_manage` patches the copy that resolved by name — the local
  winner. Before patching a skill, check whether a same-name copy exists in the other layer
  (`hermes skills list` shows the source: `local` vs `external`); fix the canonical one or
  consolidate first.
* **Ecosystem audit addition:** when auditing, run `hermes skills list` and flag any skill
  name appearing with both a `local` and an `external` source — resolve by deleting,
  renaming, or promoting before proceeding.

### Phase 5 — Audit Dependencies and Dependents

* **Dependency Audit:** Verify referenced skills, tools, scripts, references exist, and environment variables are documented.
* **Dependent Audit:** Search for references to the skill name, related skills, workflows, automations, scheduled jobs, prompts, documentation, and scripts depending on its behavior.

### Phase 6 — Design the Skill

A production skill must define: purpose, triggers, non-triggers, inputs, outputs, constraints, procedure, failure behavior, verification, and ownership boundaries.

* **Prefer:** `Verify every modified file before reporting completion.`
* **Over:** `Make sure everything is correct.`

### Phase 7 — Write the Skill

Ensure valid frontmatter using repository standards:

* **Name:** Lowercase, kebab-case, descriptive, unique, no unnecessary abbreviations.
* **Description:** ≤ 60 characters preferred; up to ~65 characters is acceptable if the description is already concise and trimming would lose clarity. One sentence, ends with a period, capability-focused, no marketing language.
* **Author:** Credit human contributor first (`Human Author, Hermes Agent`) **when creating a new skill**. For modified skills, this is optional but not required.
* **Platforms:** Determine support from actual tools, commands, scripts, and dependencies.

### Phase 8 — Structure the Body

Use a lean operational structure:

1. `# Skill Name`
2. `## When to Use`
3. `## Prerequisites`
4. `## Procedure`
5. `## Output`
6. `## Pitfalls`
7. `## Verification`

Add other sections only when they materially improve execution. For more complex skills, Quick Reference may be useful. Every important procedure must contain a checkable completion criterion.

Example:
This statement is good "Verify every changed file and report unresolved failures before completion" over "Carefully check your work"

### Phase 9 — Implement Supporting Files

Keep `SKILL.md` focused on instructions. Move substantial supporting material into `references/`, `scripts/`, or `templates/`.

### Phase 10 — Validate & Test

* **Validate:** Check frontmatter, metadata, paths, and internal consistency.
* **Test:** Run required tests for loading/execution, invalid inputs, missing dependencies, and edge cases. Never claim tests passed when they were not run.

### Phase 11 — Failure Handling

When recovery is safe, identify the failure, apply the safest valid recovery, and re-run verification. If recovery is impossible, stop the operation, preserve the current state, and report the blocker.

### Phase 12 — Ecosystem Audit

Before completion, confirm no duplicate authorities or implementations exist, references/links are valid, and dependents point to the correct authority.

---

## Upgrade Classification

| Classification | When to Use |
| --- | --- |
| **Patch** | Typo fixes, wording corrections, small non-behavioral fixes. |
| **Minor** | Backward-compatible capability additions, additional supported workflows, instruction improvements. |
| **Major** | Responsibility changes, incompatible behavior, architectural redesign, significant schema changes. |

---

## Production Quality Gate

A skill is production-ready only when all applicable gates pass:

* [ ] **Architecture:** Responsibility is unique/coherent; boundaries are clear; no unnecessary router skill exists; dependencies/dependents audited.
* [ ] **Implementation:** One canonical implementation exists; no duplicated logic; Hermes-native tools used; no machine-specific paths.
* [ ] **Skill Quality:** Triggers/non-triggers, inputs/outputs, constraints, failure behavior, and checkable completion criteria are clearly defined.
* [ ] **Metadata:** Valid frontmatter, correct name, description ≤ 60 characters preferred (up to ~64 acceptable if already concise), version appropriate, human author credited when modifying existing skill.
* [ ] **Verification:** Successfully loads, representative cases tested, expected output verified, regression check passed, ecosystem audit clear.

---

## Final Report Template

After completing the work, report structured metrics as follows:

```text
Skill: <name>
Action: <created | modified | consolidated | deprecated>
Version: <version>

Authority:
<why this skill is the authoritative owner>

Changes:
- <important change>
- <important change>

Validation:
- Structure: PASS/FAIL
- Tests: PASS/FAIL
- Behavioral verification: PASS/FAIL
- Regression check: PASS/FAIL
- Ecosystem audit: PASS/FAIL

Blockers:
<none or concise explanation>

```
> **Warning:** Never report PASS for a check that was not actually performed.
```