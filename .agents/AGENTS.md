# AGENTS.md — AROGYA Project

This file is read by the coding agent at the start of every session. It contains the
standing rules and architecture of the project — this file rarely changes.

**Before doing anything, also read:**
- `STATUS.md` — what's currently done, in progress, and next. This changes often;
  always check it fresh, don't rely on memory of a previous session.
- `docs/MASTER_PLAN.md` — full detailed specs for features and phases. Read the
  specific section relevant to your current task (STATUS.md will point you to it).
  Don't re-read the whole document for every task.

If anything in these files conflicts with what you observe in the actual code, flag
the discrepancy to the developer rather than silently picking one.

---

## 1. What This Project Is

AROGYA is a multilingual (English + Malayalam) AI hospital assistant, deployed at a real
hospital in Kerala (multi-tenant — multiple hospitals use the same deployment). It is
simultaneously the subject of an academic research paper on multi-tenant agentic
architecture for low-resource languages. This repo is the **production system**.
Research-only code (benchmarks, evaluation scripts) belongs in a separate, isolated
`backend/research/` folder — see §7.

---

## 2. Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React + TypeScript
- **Database**: PostgreSQL with the `pgvector` extension enabled. Staging is hosted on
  Render; a migration of staging to Neon is in progress — check
  `.agents/CURRENT_TASK.md` and `STATUS.md` before assuming which host is live.
- **Cache/session store**: Redis
- **LLM**: OpenAI GPT-4o-mini (current default)
- **Embeddings**: OpenAI `text-embedding-3-small`, 1536 dimensions
- **Translation**: currently Google Translate via `_translate_async()` in
  `services/translation.py`. The Malayalam output normaliser
  (`services/ml_postprocess.py`) is wired into the three English-to-Malayalam call
  sites in `api/v1/endpoints/ai.py` as of PR #17, merged 2026-08-29 — run
  `grep -n "_translate_async(" backend/app/api/v1/endpoints/ai.py` for their current
  locations. The Sarvam client itself (MASTER_PLAN.md §1.3a Task A) is not yet built;
  the API key arrived 2026-08-29, so it is no longer blocked. Task A must use
  `sarvam-translate:v1`, not `mayura:v1` — see `docs/STATUS.md` Catch-up 2026-08-23.
- **Migrations**: Alembic
- **Messaging**: Twilio WhatsApp via `services/whatsapp.py` (degrades gracefully if
  credentials are unset)

---

## 3. Key File Locations

Service extraction (§1.2) completed 2026-08-07. `ai.py` now delegates to the modules
below rather than containing this logic itself.

| Purpose | Path |
|---|---|
| Chat endpoint / orchestration | `backend/app/api/v1/endpoints/ai.py` |
| RAG + context building — `build_context()`, `build_doctor_context()`, `build_kb_context()`, `build_system_prompt_*()`, `build_fallback_instruction()` | `backend/app/services/rag.py` |
| Injection detection — `detect_prompt_injection()`, `_INJECTION_PATTERNS` | `backend/app/services/security.py` |
| Translation bridge — `_translate()`, `_translate_async()` | `backend/app/services/translation.py` |
| Session context (Redis-backed) | `backend/app/services/patient_context.py` |
| Vocabulary helpers | `backend/app/services/vocabulary.py` |
| Malayalam output normaliser — `normalise_malayalam()`, provider-agnostic, wired into the three English-to-Malayalam translate call sites in `ai.py` (PR #17, 2026-08-29)
| Booking state machine / session logic | `backend/app/services/booking.py` |
| Relevance gate (IRIS Feature 4) | `backend/app/services/relevance.py` |
| WhatsApp messaging | `backend/app/services/whatsapp.py` |
| Other services | `backend/app/services/` — `booking_rules.py`, `email.py`, `reminders.py` |
| Config | `backend/app/core/config.py` — contains `SARVAM_API_KEY`, `TWILIO_*`, (soon) `GROQ_API_KEY` |
| DB models | `backend/app/models/` — `Hospital`, `Doctor`, `DoctorSchedule`, `DoctorLeave`, `KnowledgeBase`, `Appointment`, `LabTest`, `Medicine`, `UsageLedger`, `User`, `WhatsAppLog` |
| Research code (isolated, do not import into production) | `backend/research/` |
| Current task scope (ephemeral — overwritten each task, not history) | `.agents/CURRENT_TASK.md` |

**Note:** the extraction above was a pure refactor — no signature changes, no behavior
changes. Do not further restructure `ai.py` or the `services/` modules unless the current
task explicitly says to. Don't "clean up" as a side effect of an unrelated task.

---

## 4. Database Schema Notes

- `Doctor` and `KnowledgeBase` both have a `Vector(1536)` embedding column
  (`text-embedding-3-small`).
- All patient-facing and doctor-facing queries **must** filter by `hospital_id`. Never
  write a query against `Doctor` or `KnowledgeBase` without a `hospital_id` filter, even
  in new code, even in a helper function that seems internal-only.
- Any new schema change requires an Alembic migration with a descriptive name. Do not
  apply migrations automatically to a live/production or staging database — generate the
  migration file and stop for developer review. Migrations may only be run against a
  local development database, and only if the developer has confirmed the current
  `DATABASE_URL` actually points to it.

---

## 5. Non-Negotiable Rules

1. **Multi-tenant isolation.** Every hospital has its own `hospital_id`. No query,
   context-building step, or admin feature may leak one hospital's data into another's
   response, ever — including in edge cases like fallback logic or error handling.
2. **No hardcoding of clinic-specific behavior.** Any feature requested by a specific
   hospital must be implemented as an **admin-configurable, per-hospital field or
   setting** — never as an `if hospital_id == X` branch with clinic-specific logic baked
   into shared code. The mechanism should be generically reusable by any other hospital
   tenant with different needs.
3. **Don't silently restructure.** If a task seems to require touching a much bigger
   piece of the system than described (e.g. restructuring `ai.py` or a `services/`
   module, changing an existing function signature used elsewhere), stop and flag this to
   the developer instead of just doing it.
4. **Migrations need review.** Alembic migrations are drafted, not applied, without
   explicit developer approval — especially anything touching a real/staging database.
5. **No fabricated content.** Do not invent placeholder legal/medical disclaimer wording
   and treat it as final, even if draft wording appears in `MASTER_PLAN.md`. Where
   wording is pending sign-off from hospital administration, leave the field
   empty/configurable with a clear TODO comment — do not hardcode draft wording into the
   code path.
6. **Security-sensitive logging.** Never log or store raw patient text in a security log
   or audit trail — hash it if a record needs to exist.
7. **Research code stays isolated.** Nothing under `backend/research/` may be imported by
   any file under `backend/app/`. Research code must be runnable standalone
   (`python -m backend.research.xxx`). Deleting `backend/research/` after the paper is
   published must leave the production system fully functional. Verify this by grep-
   checking for `from app.` imports in `backend/research/` before considering any
   research task done.
8. **One feature per task/diff.** Don't bundle unrelated features into the same set of
   changes, even if both appear in the same STATUS.md entry — ask if unsure.
9. **Server port management and testing.** Before starting the backend or frontend dev
   server, always first check if something is already listening on that port (8000 for
   backend, 5173 for frontend) and kill it if so, rather than starting a second instance
   on top of an existing one. Confirm each server is actually responding before running
   any test script against it.
10. **No unevidenced claims.** Do not report that something works, passes, or was
    verified without pasting the actual output that shows it. "Tested and working" with
    no command output is not a report — it is an assertion. When a task or investigation
    requires running commands, paste the **full, raw output of every command** before any
    analysis or summary. Do not quote fragments selectively. Do not write "output complete"
    and then summarise — that is the same failure. Output first, analysis after.

---

## 6. Working Process (every task, every phase, forever)

1. Read `STATUS.md` fresh — don't assume last session's status still holds.
2. Read the relevant section of `docs/MASTER_PLAN.md` for full spec detail.
3. Before writing any code, state which files you plan to create/modify and why.
   Wait for developer confirmation before proceeding.
4. Once confirmed, write `.agents/CURRENT_TASK.md` describing the confirmed scope:
   what feature, which files, and what's explicitly out of scope. This file always
   exists but holds only the current task — overwrite it, don't append to it. If the
   developer supplies a `CURRENT_TASK.md` themselves, treat it as the confirmed scope:
   read it, do not rewrite or expand it.
5. Implement only the confirmed, scoped task.
6. If schema changes are involved, generate the Alembic migration and stop — do not run
   it against anything but a confirmed local database.
7. Report back exactly which files changed, for developer review. Once accepted,
   close out per §6.11. Include a suggested review model line as specified in §10.
8. At the end of every task, draft a proposed STATUS.md update as part of your final
   report — both (a) any current-state table row that changed, and (b) a dated bullet for
   the "Catch-up" section describing what was done, in the same style as existing
   Catch-up entries. Do not edit STATUS.md directly. Present the draft entry to the
   developer for review. Only write it into the actual file if the developer explicitly
   approves it or asks you to apply it — same approval flow as Alembic migrations (§4).
9. Once the task is reported (regardless of whether the STATUS.md draft has been
   approved yet), regenerate the repomix snapshot by overwriting the existing output
   file in place — do not delete it first, then run the repomix build. This keeps the
   on-disk snapshot current; it does NOT update the developer's Claude Project, which
   requires a manual reupload. Do NOT reset `.agents/CURRENT_TASK.md` at this point — §6.11 reads its
   `## Files/areas in scope` list when staging. Reset it to an idle state (e.g. "No
   task currently in progress.") only after the close-out commit and push in §6.11
   are complete.
10. **Always cut branches from `origin/main`, not local `main`.** Local `main` may be
    ahead of `origin/main` by unpushed commits; cutting from it silently includes those
    commits in the PR. Use:
    ```
    git fetch origin
    git checkout -b fix/your-task-name origin/main
    ```
    Because this sets `origin/main` as the branch's upstream, run
    `git branch --unset-upstream` before the first push, then push with an explicit
    target: `git push -u origin HEAD:refs/heads/<branch-name>`.

    This guarantees the branch starts from exactly what GitHub has, so the PR contains
    only the current task's work. Never use `git checkout -b <name>` without an explicit
    upstream ref.

11. **Task close-out.** Once a task is reviewed and accepted, and the developer has
    approved the STATUS.md entry, you may: write that approved entry, stage the
    task's files by explicit path, commit, push to the feature branch, and open a PR
    against `main`. Then fetch CodeRabbit's review and report it in full. A finding
    may be fixed only when the fix stays inside the `## Files/areas in scope` list in
    `.agents/CURRENT_TASK.md` and fires no §10 Opus trigger. Every other finding is
    reported, not actioned — including any that needs a file outside scope, that
    disagrees with a decision taken deliberately at scoping, or that is simply wrong.
    CodeRabbit is not an authority: on PR #8 one finding was declined and one
    overridden knowingly, both correctly. Push any fixes to the same branch, then
    report three lists — fixed, declined with the reason, and deferred — and ask the
    developer to merge.

    Never `git add -A`, `git add .`, or `git add -u` — stage only files named in
    `.agents/CURRENT_TASK.md` under `## Files/areas in scope`, plus `docs/STATUS.md`,
    which is a standing exception because every task writes it and it is therefore
    never listed as task scope. Nothing else may be staged. If any other file is
    modified, leave it untouched and commit around it. Paste `git show --name-only
    HEAD` after committing.

    Note that `git add docs/STATUS.md` stages the whole file. Before staging it, run
    `git diff docs/STATUS.md` and check whether it contains changes beyond the
    approved entry. If it does, STOP: report exactly what the unrelated changes are
    and ask the developer whether to include them, commit separately, or set them
    aside. Do not stage unrelated changes on your own judgement, and do not stash,
    revert or discard them either.

    Run `git branch --unset-upstream` before pushing if the branch was created with
    `git checkout -b <name> origin/main`, which sets `origin/main` as upstream and
    would make a bare `git push` target `main`. Then push with an explicit target:

    ```
    git push -u origin HEAD:refs/heads/<feature-branch>
    ```

    Never use a bare `git push` in close-out.

    **You may never merge a pull request.** That is the developer's action, always,
    including when CodeRabbit reports no issues.

    
    Once the developer approves the drafted entry, the agent writes it into
    STATUS.md verbatim as approved, then pastes `git diff docs/STATUS.md` to prove
    that only the approved text landed. The agent may not reword, condense, expand
    or reorder an approved entry while writing it.

---

## 7. Broader Roadmap (for context — see docs/MASTER_PLAN.md for detail)

- **Phase 1 (product):** Patient Personalisation, IRIS clinic features, service
  extraction (`ai.py` → `services/`), Sarvam translation upgrade, security hardening,
  multi-tenant isolation hardening.
- **Phase 2 (research, later):** `backend/research/` — retrieval benchmark, LLM
  benchmark, translation evaluation, bias analysis, tenant isolation test, load test,
  security evaluation. Fully isolated from production, per §5.7.

---

## 8. Conventions

- Python: follow existing style in `ai.py` and `services/` — do not introduce a new
  formatting style in new files.
- New service modules should be typed, with clear function boundaries — no god-files.
- Admin-facing config fields: always give them a sensible default (usually empty
  string/false), never assume a value if the developer hasn't provided one.
- Commit/PR scope: keep each feature's changes isolated and reviewable.

---

## 9. When In Doubt

Ask the developer rather than guessing, especially for:
- Anything involving real patient data or PII
- Anything that would change behavior for hospitals other than the one being worked on
- Any migration or command that would touch a non-local database
- Disclaimer/legal wording not yet confirmed by hospital administration

- **No commands against a non-local database.** Do not run any command against a
  database that is not a confirmed local development database — this includes Alembic,
  `psql`, `pg_dump`, `pg_restore`, `CREATE EXTENSION`, and any script or tool that opens
  a connection. Neon, Render, and any other hosted instance are non-local. For a
  non-local target, either the developer runs the command themselves, or the developer
  explicitly approves it in-chat after the exact target connection string has been
  stated and confirmed. Never infer approval from an earlier approval for a different
  command or a different target.

---

## 10. Suggested Review Model

At the end of every task report (§6.7), state which Claude model the developer should use
to review the diff. Output it on its own line, in exactly this format:

```
Suggested review model: <Opus 5 | Sonnet 5 | Haiku 4.5>, <low | medium | high | xhigh> effort — <the trigger that fired>
```

**This is a mechanical classification, not a judgment call.** Decide the tier purely from
which files and patterns the diff actually touches, using the lists below. Do not
downgrade a tier because the change felt small, safe, or obvious to you. If a listed
trigger fired, name that tier regardless of how confident you are in the code.

### Opus 5 — name this tier if the diff does ANY of the following

- Adds or modifies any query against `Doctor`, `KnowledgeBase`, `Appointment`, or
  `LabTest`
- Adds, removes, or edits any `hospital_id` filter, or adds any code path that returns
  tenant-scoped data (including helpers, fallbacks, and error paths)
- Creates or edits an Alembic migration, or runs any migration command
- Touches logging, audit trails, or `SecurityLog`, or handles raw patient text anywhere
- Touches `detect_prompt_injection()`, `_INJECTION_PATTERNS`, or `services/security.py`
- Changes an existing function signature, or moves code between modules
- Adds or edits disclaimer, legal, or medical wording fields
- Touches anything under `backend/research/`, or any import crossing the
  `app/` ↔ `research/` boundary
- Touches auth, session tokens, or Redis session key patterns
- Touches `DATABASE_URL`, connection configuration, or any non-local database

### Sonnet 5 — default tier for real logic changes not listed above

New service functions, booking-flow changes, frontend admin UI, new config fields,
translation logic, ordinary bug fixes.

### Haiku 4.5 — mechanical changes only

Formatting, comments, README or docs text, renaming a variable within a single file,
STATUS.md draft wording.

### Effort level

Pair the effort level to the tier:

| Tier | Effort | Escalate to xhigh when |
|---|---|---|
| Opus 5 | `high` | Two or more Opus triggers fired in the same diff, **or** the diff combines a migration with tenant-scoped query changes, **or** it touches `services/security.py` / `_INJECTION_PATTERNS` |
| Sonnet 5 | `medium` | Never — if it needs more, the tier is wrong |
| Haiku 4.5 | `low` | Never |

Do not name `max` effort. If a diff seems to warrant it, that is a signal the change is
too large for one task and should have been split under §5.8 — say so instead.

### Rules for choosing

- If triggers from more than one tier fire, **name the highest tier**.
- If you are unsure which tier applies, **name the higher one**. Never round down.
- The developer has a limited Opus budget — do not name Opus 5 unless a trigger in the
  Opus list actually fired. Do not name it defensively or "just in case."
- Name exactly one tier and one trigger. If several Opus triggers fired, cite the most
  significant one.
- Cite the tier from the rules in this section. If `.agents/CURRENT_TASK.md` already
  names a suggested tier and your own classification differs, say so explicitly rather
  than silently copying the task file's tier.

---

## 11. Superpowers Plugin Precedence

1. AGENTS.md §5 and §6 take precedence over any Superpowers skill instruction.
   Where a Superpowers skill says an action is mandatory and AGENTS.md forbids or
   gates it, AGENTS.md wins. Flag the conflict to the developer rather than
   resolving it silently.
2. subagent-driven-development and executing-plans must not run autonomously
   across more than one feature. AGENTS.md §5 rule 8 (one feature per task/diff)
   is not suspended by an approved Superpowers plan. Stop at the end of each
   feature and report.
3. The §6 step-3 gate stands: state which files you plan to create or modify and
   wait for developer confirmation, even when a Superpowers plan already exists.
   An approved plan is not approval to begin writing code.
4. finishing-a-development-branch may push to a feature branch and open a pull
   request without a further approval step, since both are reversible and neither
   changes `main`. It must NOT merge, force-push, delete a branch or worktree, push
   to `main`, or alter branch protection — those are developer-only actions. See
   §6.11 for the full close-out sequence.
5. Alembic migrations remain draft-only per §5 rule 4. No Superpowers workflow,
   including a clean-test-baseline check, authorises applying a migration.
6. Superpowers must not be used on IRIS clinic-facing features whose wording is
   still pending clinic sign-off. §5 rule 5 (no fabricated placeholder
   legal/medical text) applies with full force to any text a Superpowers skill
   proposes.
7. test-driven-development is adopted for new work under §1.4 and §1.5 and for
   backend/research/. It is not retroactively applied to existing code, and it
   does not authorise deleting existing code that lacks tests.

---

## 12. Claude Code Orchestration — The Closed Loop

Work is scoped in Claude Chat, executed by Claude Code and Antigravity without
supervision, and returns to Claude Chat only when a decision is genuinely the
developer's to make.

The developer talks only to Claude Chat. Nothing below Claude Chat asks the developer
a question directly.

### 12.1 The layers

| Layer | Is | Does | Never does |
|---|---|---|---|
| **Developer** | The decision-maker | Approves scope, approves the STATUS.md entry, makes every escalated decision, merges | — |
| **Claude Chat** | Planning and decision layer | Scopes the task, writes `.agents/CURRENT_TASK.md` and `.agents/DECISION.md`, answers halts, reads git state and files under `.agents/` and `docs/` (§12.16, §12.17), and may stage and commit during §6.11 close-out | Write code. Write any file under `backend/` or `frontend/`. Push, open a PR, or merge. Move HEAD or change branches |
| **Claude Code** | Execution driver | Plans the mechanics, dispatches Antigravity, reads its raw output, re-dispatches on error, resolves minor decisions per §12.4, reviews at the end, writes the handoff on a halt, and runs close-out per §6.11 — approved STATUS.md entry, staging, commit, push, PR, CodeRabbit triage | Merge a PR. Force-push, except `--force-with-lease` on its own unmerged feature branch (§12.10). Push to `main`. Delete a branch. `git add -A`. Any migration. Any non-local DB command. Any documentation write before the developer has approved the text (§12.15). Any edit to `.agents/CURRENT_TASK.md` or `.agents/DECISION.md`. Resolve anything §12.5 names |
| **Antigravity** | Mechanical executor | Writes the code named in the plan | Decide anything. Deviate from `CURRENT_TASK.md` |

Claude Code has shell access so it can run Antigravity and read its output. That
access exists to remove the developer from the middle of the error loop — not to
widen what Claude Code may change. See §12.10.

### 12.2 The loop

1. **Scope.** The task is scoped in Claude Chat. `.agents/CURRENT_TASK.md` is written
   there, per §6.4. Nothing below this point starts until the developer confirms it.
2. **Run.** Claude Code dispatches Antigravity, reads its raw output, re-dispatches on
   error, and resolves minor decisions itself per §12.4. This continues without
   developer involvement for as long as no §12.5 halt condition is reached.
3. **Halt.** On a §12.5 condition, Claude Code stops, writes `.agents/LOOP_HANDOFF.md`
   (§12.6), and does nothing further.
4. **Decide.** The developer brings `LOOP_HANDOFF.md` into Claude Chat. The decision is
   made there. Claude Chat writes `.agents/DECISION.md` (§12.7).
5. **Resume.** Claude Code reads `DECISION.md`, appends it to the dispatch log, and
   continues from where it halted. Steps 2–5 repeat as needed.
6. **Review and report.** At the end of the task, Claude Code reviews its execution
   against the plan, and reports — including every minor decision it took under
   §12.4, batched into one list. The developer reads them once, at the end, not six
   times mid-run.
7. **Close out.** Claude Code drives it on the feature branch, per §6.11 and §12.10:
   run the documentation sweep, write the approved STATUS.md entry, append
   `MASTER_PLAN.md` §9 if the task file scoped one, stage by explicit path, commit,
   push, open the PR, backfill the real PR number and commit hashes, then fetch
   CodeRabbit's review and report it in full. It may fix a finding only when the fix
   stays inside the task's `## Files/areas in scope` and fires no §10 Opus trigger;
   everything else is reported, not actioned (§6.11). It never
   merges. Merging the PR, deleting the branch, and re-uploading any changed
   governing document to the Claude Project are the developer's, always.

   A task file may narrow this. `MASTER_PLAN.md` §1.3a keeps close-out manual for the
   three Sarvam tasks, deliberately. A narrowing in a task file or plan section wins
   over this step — it is a floor, not a ceiling.

### 12.3 Which work goes where

- **Fully mechanical work** — every file and line already named, formatting,
  `STATUS.md` wording, repomix regeneration, a rename inside one file — runs in
  Antigravity alone, with no Claude Code reasoning involved. This is most of the
  token volume and none of the risk.
- **Work containing a decision** is reasoned by Claude Code first, written into the
  plan, then executed mechanically by Antigravity.

The split is by whether the task needs judgement, not by which area of the codebase
it touches.

Reviews read only the changed files plus their direct callers. Never the repomix
snapshot — it goes stale, and re-reading it is the largest avoidable cost in the
review path. Review runs once, at the end, not mid-task.

### 12.4 Decisions Claude Code takes on its own

**Default: decide it, log it, keep going.** Do not halt for a small decision. An
interruption costs the developer more than a reversible wrong choice caught at
review.

A decision is Claude Code's to take if it is on the whitelist below, **or** it passes
the reversibility test — and it is not named in §12.5. §12.5 always wins.

**Whitelist — take these without asking:**

- Wording of a log message, comment, docstring or error string that is not
  patient-facing, legal, or medical.
- Local variable and helper names inside a file already in scope.
- The order in which the scoped edits are applied.
- Test fixture values, as long as they are obviously synthetic (§5.10).
- Which throwaway/scratch script to write for evidence capture, and how.
- Formatting and import ordering consistent with the existing file (§8).
- Retry strategy for a transient failure — network, port in use, flaky start.
- Which of two equivalent phrasings satisfies an instruction already given in
  `CURRENT_TASK.md`.

**Reversibility test — for anything not on the whitelist, all four must be true:**

1. It is undone by editing one file, with no migration and no data change.
2. It changes nothing a patient sees, and nothing another tenant sees.
3. It touches no §10 Opus trigger.
4. It stays inside the `## Files/areas in scope` list in `CURRENT_TASK.md`.

If any of the four is false, it is a §12.5 halt.

**Logging them.** Every decision taken under this section is appended to
`.agents/DECISIONS_TAKEN.md` as it happens — one line each: what was decided, which
whitelist item or test justified it, and the file it affected. The developer is never
required to read this mid-run; it exists so a task that goes sideways can be
reconstructed. The same list is repeated in the end-of-task report (§12.2 step 6).

`DECISIONS_TAKEN.md` is reset at the start of each task, not appended across tasks.

### 12.5 Decision points — what forces a halt

Claude Code halts and writes a handoff on any of:

1. **Any Alembic migration**, drafted or applied. §5.4 is unchanged by this section.
2. **Any §10 Opus trigger** — tenant-scoped queries, `hospital_id` filters, logging
   or raw patient text, `services/security.py`, function signature changes,
   disclaimer or legal wording, `backend/research/` boundary crossings, auth or Redis
   session keys, `DATABASE_URL`.
3. **Any scope change** beyond the `## Files/areas in scope` list in
   `CURRENT_TASK.md`. §5.3 and §5.8 apply in full.
4. **The same error hit three times.** Stop, hand off the three attempts with their
   raw output, and do not attempt a fourth. Repeated failure means the plan is wrong,
   not that the retry needs rewording.
5. **Anything in §9** ("When In Doubt") — real patient data, cross-tenant behaviour
   change, a non-local database, unconfirmed disclaimer wording.
6. **Anything that fails the §12.4 reversibility test** and is not on the §12.4
   whitelist.

A halt is a full stop. Claude Code does **not** continue with other in-scope work
while waiting. Partial work built on an unresolved assumption is worse than an idle
loop — it produces a diff where some of it presumes a decision that was never made.

When in doubt between §12.4 and §12.5, halt. The §12.4 default is for decisions that
are clearly small, not for close calls.

### 12.6 `.agents/LOOP_HANDOFF.md` — the halt file

Written by Claude Code. Overwritten each halt, not appended to. Must be
**self-contained**: Claude Chat must be able to answer it without opening the repo.

Required sections, in this order:

```
# Handoff — <UTC timestamp>

## Task
<the CURRENT_TASK.md feature line, verbatim>

## Halt trigger
<which §12.5 condition fired, by number, and the one-line reason>

## Where execution stopped
<the last completed step from CURRENT_TASK.md ## Order, and what was next>

## The decision needed
<one sentence, phrased as a question>

## Options seen
<each option, what it costs, what it risks. No invented third options>

## Recommendation
<Claude Code's own pick and why — a recommendation, not an action>

## Evidence
<the raw command output, diff hunk, or error trace that triggered the halt.
 Full and unedited. No selective quoting — §5.10>

## Rules implicated
<the §5, §9 or §10 rule numbers this touches>

## Files touched so far this task
<explicit paths, and whether each is complete or mid-edit>

## Minor decisions taken since the last handoff
<the §12.4 lines, so the developer sees them in context>
```

No raw patient text in a handoff file, ever — §5.6. If the evidence would contain it,
the handoff says so and reports character counts instead.

### 12.7 `.agents/DECISION.md` — the resume file

Written by Claude Chat once the developer has decided. Overwritten each time.

```
# Decision — <UTC timestamp>

## Answers
<the halt question, and the decision, unambiguous>

## Scope effect
<either "no change to CURRENT_TASK.md" or the exact lines that change>

## Resume from
<the step in CURRENT_TASK.md ## Order to continue from>
```

Claude Code resumes only on a `DECISION.md` newer than the current `LOOP_HANDOFF.md`. If
`DECISION.md` does not answer the question asked, Claude Code halts again rather than
interpreting it.

If a decision changes scope, `CURRENT_TASK.md` is edited by Claude Chat, not by Claude
Code, and the change is stated in `## Scope effect` so it is auditable.

### 12.8 Dispatch log

Every instruction Claude Code sends to Antigravity, and every raw output it reads
back, is appended to a timestamped file under `.agents/runs/`.

- Append-only. Entries are never edited or deleted.
- Each entry records: timestamp, instruction sent, raw output received, and whether a
  halt fired.
- Every `LOOP_HANDOFF.md` and `DECISION.md` is copied into the log at the moment it is read
  or written, so the decision history survives the next overwrite.
- `.agents/runs/` is already gitignored (PR #9, merged 2026-08-22), so none of this
  reaches a diff.

The purpose is reconstruction — the developer must be able to see exactly what
happened without having watched it live.

### 12.9 Review tier — ratchet only

- Antigravity emits the §10 suggested-review-model line mechanically at the end of its
  work, exactly as §10 already requires.
- Claude Code **may escalate** that tier, naming the §10 trigger that justifies it.
- Claude Code **may never lower** it. If its own §10 classification comes out lower
  than Antigravity's, Antigravity's tier stands and the disagreement is reported as a
  finding.
- When **no Antigravity dispatch runs** and Claude Code did the work itself, there is
  no independent tier line to ratchet from. Claude Code still emits its own §10 line,
  and must say plainly in the report that no floor existed and the classification is
  unratcheted. It may not present its own line as if it were a second opinion. One
  classification stated once is not two that agreed.

A reviewer allowed to lower its own tier will round down when a change feels small.
That is the exact failure §10 exists to prevent.

### 12.10 Hard limits on Claude Code

Shell access grants none of the following. These are absolute, and §12.4 never
authorises any of them:

- **Git writes are limited to a feature branch.** Claude Code MAY run `add` (named
  paths only, never `-A`, `.`, `-u` or a glob), `commit`, `push` to a feature branch,
  `fetch`, `rebase origin/main`, and `gh pr create`. It MAY NOT `merge`, push to
  `main`, force-push except `--force-with-lease` on its own unmerged feature branch,
  `reset --hard`, `checkout` a different branch, `worktree add`, delete any branch, or
  alter branch protection. **Merging a PR is the developer's action, always, without
  exception** — §6.11. A reviewer that needs a different revision uses `git show`,
  `git diff` and `git log`, and reports that it cannot see something rather than moving
  HEAD to reach it.
- **No migration command** — not `alembic upgrade`, `downgrade`, or
  `revision --autogenerate`, against anything. §5.4.
- **No command against a non-local database.** §9 applies in full. Neon, Render and
  any other hosted instance are non-local.
- **No documentation write before approval.** `docs/STATUS.md` and
  `docs/MASTER_PLAN.md` are drafted, presented, and written into only after the
  developer has explicitly approved the text — see §12.15. Writing an unapproved draft
  into either file is a §12.5 halt condition in retrospect, not a minor decision.
- **No edit to `.agents/CURRENT_TASK.md` or `.agents/DECISION.md`.** Both are written by
  Claude Chat and read by Claude Code. §6.4 forbids rewriting a developer-supplied scope
  file; §12.7 makes the resume file Claude Chat's. See §12.15 for why these two sit on
  the other side of the line from STATUS.md.

### 12.10a Antigravity's scoped `command(...)` grant

Reverses the deliberate withholding recorded in Catch-up 2026-08-28, so mechanical work
can actually run in Antigravity per §12.3 instead of falling to Claude Code by default.
Lives in `~/.gemini/antigravity-cli/settings.json`, outside the repo — developer-edited
only, per §12.15's reasoning applied to permission files: an agent that can widen its own
grant has no grant.

**ALLOW, enumerated exactly. A wildcard is a door in the wall:**
- `command(python backend/run_ml_postprocess_test.py)`
- `command(python backend/run_translation_test.py)`
- `command(python backend/run_e2e_test.py)`
- `command(python backend/run_malayalam_test.py)`
- `command(grep)`, `command(rg)`, `command(ls)`, `command(dir)`, `command(cat)`,
  `command(type)`, `command(findstr)`
- `command(git status)`, `command(git diff)`, `command(git log)`, `command(git show)`
- `command(npx repomix)`

Never bare `command(python)` — a one-token prefix matches every possible Python
invocation, and `python -c` is an unrestricted shell. Never bare `command(git)` — same
reasoning; only the four read-only subcommands above are granted.

**DENY, unconditionally, regardless of any instruction Antigravity is given:**
- All deletion: `rm`, `del`, `rmdir`, `Remove-Item`, `ri`, `erase`, `rd`
- `command(alembic)` — §5.4. Drafted, never applied, and never by Antigravity.
- `command(psql)`, `command(pg_dump)`, `command(pg_restore)` — §9. Neon and Render are
  non-local.
- All network: `curl`, `curl .*`, `curl.exe`, `wget`, `Invoke-WebRequest`, `iwr`
- All git writes: `add`, `commit`, `push`, `merge`, `checkout`, `reset`, `branch`,
  `worktree`, `rebase`, `stash`
- `command(sudo)`

**NOT GRANTED:**
- Dev servers (`uvicorn` on port 8000, `vite`/`npm run dev` on port 5173). §5.9 requires
  killing an existing port listener before starting one, and that kill command's argument
  is a process ID discovered only at runtime — a permission pattern can either hardcode
  one specific PID (useless next time) or wildcard the PID, which grants unrestricted
  kill-any-process rather than anything scoped to a port. Port-clearing stays a manual,
  developer-performed step.
- `python -m backend.research.*` — Phase 2 has not started (STATUS.md Phase 2 section).

**Why deletion is denied outright, not scoped to non-recursive.** Permission patterns
match by whitespace-separated token, each anchored as `^(?:pattern)$`, evaluated as a
token-count prefix — so any `command(rm)` or `command(del)` allow permits arbitrary
trailing flags, since only the tokens explicitly named in the pattern are constrained.
On this machine's shell (PowerShell), `rm` and `del` are built-in aliases for
`Remove-Item`, which takes `-Recurse`/`-Force` — parameter names that match no POSIX
deny token (`-r`, `-rf`, `-R`). There is no pattern that permits a single-file delete
without also permitting a recursive one. The 2026-08-28 gap (three scoped deletions
requiring the developer's hand) therefore stays manual, rather than trading it for
recursive-delete capability on the repo tree.

**Why the localhost network allowance was withdrawn.** A pattern like
`command(curl http://localhost.*)` fails to match `curl -s http://localhost:8000`,
because the second whitespace-separated token is `-s`, not the URL — enforcing
"localhost only" would mean enumerating every flag ordering the model might generate,
which breaks by accident, not only adversarially. All direct network tools are denied
outright instead.

**Why `command(*)` on the ask list is not the answer.** Antigravity's own documentation
states permission conflicts resolve as "Deny > Ask > Allow" — an `Ask` entry on `*` would
outrank every `Allow` entry above, prompting before every one of the enumerated scripts
and tools and defeating unattended running entirely.

**Step 3b result (2026-09-02), established empirically, not assumed.** With the real
`~/.gemini/antigravity-cli/settings.json` unmodified (zero `command(...)` entries at the
time), Antigravity was dispatched headlessly (`agy --print`) in the isolated
`D:\scratch-loop-test` sandbox to run `whoami` — a command matching neither an allow nor
a deny entry. Result: `jetski: no output produced — a tool required the "command"
permission that headless mode cannot prompt for, so it was auto-denied.` An unmatched
command is refused outright in headless dispatch, not left pending and not executed.
This confirms, rather than merely corroborates, the 2026-08-28 observation that
Antigravity was blocked, not permitted, on ungranted commands. This result is specific to
headless (`--print`) dispatch, which is how Claude Code invokes Antigravity under this
section; interactive-mode behavior for an unmatched command was not tested.

**Residual risks, accepted knowingly:**
- Antigravity may still reach `api.openai.com` and `api.sarvam.ai` indirectly if a dev
  server it starts is running, spending real credits under the developer's keys — direct
  network tools are denied, but traffic through the running application itself is not
  prevented.
- These limits are enforced by the permission file, not by Antigravity's cooperation.
  §12.1 gives Antigravity no decision authority; a rule it must choose to follow is not a
  limit.

### 12.11 Precedence

§5 and §6 outrank everything in §12. Where continuing the loop would require breaking
a rule in §5 or §6, the loop halts instead — always, without exception.

§11 (Superpowers Plugin Precedence) is unchanged and still governs Antigravity's
plugin behaviour. Where §11 and §12 both apply, the stricter reading wins.

### 12.12 Model policy

Claude Code does not choose its own model. This is fixed:

| Job | Model | Why |
|---|---|---|
| Loop driver — dispatching Antigravity, reading raw output, re-dispatching, taking §12.4 decisions | **Sonnet** | High volume, low judgement. Most of the token spend and least of the risk |
| First-pass review at end of task (§12.13) | **Sonnet** | A mechanical checklist — did execution match the plan |
| Second review — adversarial, in Claude Chat | **Per §10**, reaching Opus only when a §10 Opus trigger actually fired | This is where judgement is genuinely needed |

**Opus is never run inside Claude Code.**

**Budget cap.** On the Claude Pro plan, Claude Code and Claude Chat draw from the same
usage pool — every token the loop spends is a token unavailable for the §10 review. The
loop is therefore capped: if a single task reaches **three halt cycles**, Claude Code
stops and reports rather than continuing. Three halts means the scope was wrong, and
grinding on risks exhausting the budget before the diff has been reviewed at all.

### 12.13 First-pass review report — fixed format

Claude Code's end-of-task review (§12.2 step 6) outputs exactly these seven sections, in
this order, matching the `review-skill` format so the second review always has the same
shape to check:

1. **Findings**
2. **Verdict**
3. **Tier check**
4. **STATUS.md check**
5. **Follow-up prompt**
6. **Follow-up model**
7. **Plain-English explainer**

Rules for the report:

- Every finding cites file and line. A finding with no location is not a finding.
- Verdict is one of: `accept as-is`, `accept with fixes`, `reject`. There is no hedged
  fourth option.
- Tier check states Antigravity's §10 line verbatim, and whether Claude Code escalated
  it and why, per §12.9. It may never lower it.
- STATUS.md check confirms the §6.8 draft entry exists and has **not** been written into
  the file.
- Follow-up prompt is complete and copy-pasteable, or the section reads "none needed".
  Not a sketch the developer has to rewrite.
- No claim of passing, working or verified without the raw output pasted — §5.10.
- The §12.4 minor-decision list is appended under **Findings**, not buried elsewhere.

This report is the *input* to the second review. It is not a substitute for it.

### 12.14 What this does and does not save

This removes the developer from the middle of the error loop, stops stale or partial
pastes reaching a reviewer, and keeps small decisions from becoming interruptions.
That is the win.

It does **not** reduce Claude token use per diff — a reviewer reading files directly
generally uses more than a pasted diff, not less. The saving comes from §12.3: fully
mechanical work runs in Antigravity with no Claude involvement at all.

### 12.15 Documentation the driver may write

Claude Code writes documentation. The developer approves it first. The dividing line is
not how risky a file looks — it is whether the file **describes** the work or
**governs** it.

**Descriptive — Claude Code writes, after approval:**

- `docs/STATUS.md`
- `docs/MASTER_PLAN.md`
- any other documentation file named in `.agents/CURRENT_TASK.md` under
  `## Files/areas in scope`

**Governing — Claude Code never writes, approved or not:**

- `.agents/CURRENT_TASK.md`
- `.agents/DECISION.md`

The reason for the split is not caution, it is measurability. Every scope check in the
review layer — files touched outside scope, anything from `## Do NOT touch`, work
pulled from the `## Manual` bucket — compares the diff against `CURRENT_TASK.md`. If
the thing being scoped can edit its own scope, that comparison proves nothing: a diff
and a task file can always be made to agree by moving the task file. The same logic
applies to `DECISION.md`, which is the record of what the developer actually decided. A
descriptive file has no such role — a wrong line in `STATUS.md` is a wrong line, not a
broken check.

**The approval gate, in order:**

1. Draft the entry per §6.8 and present it. Do not write it.
2. Wait for the developer to approve it explicitly. Silence is not approval. "Looks
   fine", "ok", or moving on to the next topic is not approval. If it is ambiguous
   whether approval was given, it was not.
3. Write the approved text **verbatim**. No rewording, condensing, expanding or
   reordering while writing it (§6.11).
4. Paste `git diff` for that file, proving only the approved text landed.
5. If that diff shows anything beyond the approved text, halt under §12.5 and report
   exactly what the extra changes are. Do not stage, revert, stash or discard them.

**Append-only rules survive this section unchanged.** `STATUS.md`'s Catch-up log is
append-only: add a new dated entry, never edit or delete an existing one, even when it
has become wrong. `MASTER_PLAN.md`'s `## 9. Unplanned / Ad-hoc Work` is append-only and
no other section of that document may be edited or renumbered.

**The §9 append is already approved at scoping time.** `CURRENT_TASK.md`'s
`## MASTER_PLAN.md update` section states the append, and the developer approves that
file before any work starts. That is the approval — no second gate is needed mid-run.
This is the one documentation write that does not pause for a fresh yes, and it is not
an exception to the gate above: the approval simply happened earlier.

**Regenerating the repomix snapshot (§6.9) is not a documentation write** and needs no
approval. It overwrites a generated artifact, not a document anyone reads directly.

### 12.16 Claude Chat's filesystem access

Claude Chat reaches the repository through a local MCP server
(`@modelcontextprotocol/server-filesystem`), scoped to exactly two directories:
`.agents/` and `docs/`. Added 2026-08-30, repaired 2026-09-01.

**Scope is enforced by the server, not by instruction.** Paths outside those two
directories are refused by the server itself. `backend/app/` and `frontend/src/` are
therefore unreachable to Claude Chat, by construction — it reads source only as a
diff, through §12.17's git server.

**The server has write tools and they are deliberately enabled.** This is how Claude
Chat writes `.agents/CURRENT_TASK.md` and `.agents/DECISION.md`, the two files
§12.15 assigns to it. It is also how it reads `LOOP_HANDOFF.md`, `STATUS.md` and
`MASTER_PLAN.md` off disk rather than from a stale Project upload.

**Launch note.** The server must be launched by absolute path to `npx`. On this
machine `npx` lives at `D:\npx.cmd`, which is not on the PATH that Claude Desktop's
child processes inherit; a bare `npx` in `claude_desktop_config.json` fails silently
at launch, leaving valid JSON and no tools. That was the 2026-08-31 to 2026-09-01
outage.

**Writing `docs/STATUS.md` from Claude Chat remains gated by §12.15's approval
sequence.** Reach is not authority: the server allows the write, the approval gate
decides whether it happens.

### 12.17 Claude Chat's git access

Claude Chat reaches git through a second local MCP server (`mcp-server-git`,
official, from `modelcontextprotocol/servers`), scoped to this repository. Added
2026-08-31.

**This server is local git only.** It has no network reach: no `push`, no remote, no
GitHub API. Opening a pull request and reading a CodeRabbit review are therefore
impossible from Claude Chat, and remain Claude Code's under §6.11 or the
developer's. A third server would be required to change that.

**Tools Claude Chat may use freely, at any time:** `git_status`, `git_log`,
`git_diff`, `git_diff_staged`, `git_diff_unstaged`, `git_show`, `git_branch`.

**Tools Claude Chat may use only during §6.11 close-out, and only after the
developer has approved the STATUS.md entry:** `git_add` (named paths only, never
`-A`, `.`, `-u` or a glob), `git_commit`.

**Tools Claude Chat may never use:** `git_reset`, `git_checkout`,
`git_create_branch`, `git_init`, and any future tool that rewrites history, moves
HEAD, or changes which branch is checked out. A reviewer that needs a different
revision uses `git_show` and `git_diff`, and reports that it cannot see something
rather than moving HEAD to reach it.

**Merging is never Claude Chat's.** Same as §6.11 and §12.10 — the developer merges,
always, without exception, including when CodeRabbit reports no issues.

**Why read access is granted at all.** On 2026-08-31, Claude Chat produced a branch-
move sequence that aborted, because it did not know `origin/main` had advanced to
`12b7c66` (PR #18) and had assumed uncommitted docs files would survive a checkout.
The failure was a gap in visibility, not in authority.

### 12.18 One Claude Chat session at a time

`.agents/CURRENT_TASK.md` and `.agents/DECISION.md` are written by Claude Chat
(§12.15, §12.16). Neither has any locking, versioning or conflict detection: a write
is a full overwrite.

Two concurrent Claude Chat sessions therefore overwrite each other silently. On
2026-08-31 this happened — a second session wrote a repo-hygiene scope into
`CURRENT_TASK.md` while a first session was mid-task on the IRIS design tokens.
Claude Code, reading the file cold, correctly refused to append a paused-state
section for a task the file no longer described.

**Rule:** only one Claude Chat session may hold a task at a time. Before writing
`CURRENT_TASK.md`, Claude Chat reads it first and reports what it is about to
replace. If the existing content describes a different task, that is a stop-and-ask,
not an overwrite.

Claude Code is not required to reconcile a task file that does not match the work in
front of it. Refusing and reporting is the correct behaviour, and is what §12.15's
scope check depends on.