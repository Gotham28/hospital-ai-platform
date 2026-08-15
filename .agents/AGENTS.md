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
  `services/translation.py`; Sarvam AI upgrade not yet started (see
  `docs/MASTER_PLAN.md` §1.3)
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
   requires a manual reupload. Also reset `.agents/CURRENT_TASK.md` to an idle state
   (e.g. "No task currently in progress.") now that the task is closed.
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
    against `main`. Then fetch CodeRabbit's review and report it in full without
    fixing anything.

    Never `git add -A`, `git add .`, or `git add -u` — stage only files named in
    `.agents/CURRENT_TASK.md` under `## Files/areas in scope`, plus `docs/STATUS.md`,
    which is a standing exception because every task writes it and it is therefore
    never listed as task scope. Nothing else may be staged. If any other file is
    modified, leave it untouched and commit around it. Paste `git show --name-only
    HEAD` after committing.

    Note that `git add docs/STATUS.md` stages the whole file. If it already carries
    unrelated uncommitted changes, they will be included — say so in the task report
    rather than attempting to separate them.

    Run `git branch --unset-upstream` before pushing if the branch was created with
    `git checkout -b <name> origin/main`, which sets `origin/main` as upstream and
    would make a bare `git push` target `main`. Then push with an explicit target:

        git push -u origin HEAD:refs/heads/<feature-branch>

    Never use a bare `git push` in close-out.

    **You may never merge a pull request.** That is the developer's action, always,
    including when CodeRabbit reports no issues.

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
