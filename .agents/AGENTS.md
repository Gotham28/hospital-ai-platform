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
- **Database**: PostgreSQL on Render, with the `pgvector` extension enabled
- **Cache/session store**: Redis
- **LLM**: OpenAI GPT-4o-mini (current default)
- **Embeddings**: OpenAI `text-embedding-3-small`, 1536 dimensions
- **Translation**: currently Google Translate via `_translate_async()`; Sarvam AI upgrade
  in progress (see `docs/MASTER_PLAN.md` §1.3)
- **Migrations**: Alembic

---

## 3. Key File Locations

| Purpose | Path |
|---|---|
| Main AI logic (RAG, translation, booking, security, intent) | `backend/app/api/v1/endpoints/ai.py` |
| System prompt builders | `build_system_prompt_english()`, `build_system_prompt_malayalam()`, `build_fallback_instruction()` — inside `ai.py` |
| Context builder | `build_context(request, db)` — inside `ai.py` |
| KB retrieval | `build_kb_context()` — inside `ai.py` |
| Doctor retrieval | `build_doctor_context()` — inside `ai.py` |
| Injection detection | `detect_prompt_injection(text)` using `_INJECTION_PATTERNS` — inside `ai.py` |
| Translation bridge | `_translate_async(text, source, target)` — inside `ai.py` |
| DB models | `backend/app/models/` — `Hospital`, `Doctor`, `KnowledgeBase`, `Appointment`, `LabTest` |
| Config | `backend/app/core/config.py` — contains `SARVAM_API_KEY`, (soon) `GROQ_API_KEY` |
| Existing services | `backend/app/services/` — currently `booking_rules.py`, `email.py`, `reminders.py` |
| Research code (isolated, do not import into production) | `backend/research/` |

**Note:** `ai.py` is currently a large (~800+ line) file mixing many concerns. This is
scheduled to be split into `services/rag.py`, `services/patient_context.py`,
`services/translation.py`, `services/booking.py`, `services/security.py` — **do not do
this refactor unless the current task explicitly says to.** Don't "clean up" ai.py as a
side effect of an unrelated task.

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
   piece of the system than described (e.g. refactoring `ai.py`, changing an existing
   function signature used elsewhere), stop and flag this to the developer instead of
   just doing it.
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
9. **Server Port Management and Testing.** Before starting the backend or frontend dev server, always first check if something is already listening on that port (8000 for backend, 5173 for frontend) and kill it if so, rather than starting a second instance on top of an existing one. Confirm each server is actually responding before running any test script against it.

---

## 6. Working Process (every task, every phase, forever)

1. Read `STATUS.md` fresh — don't assume last session's status still holds.
2. Read the relevant section of `docs/MASTER_PLAN.md` for full spec detail.
3. Before writing any code, state which files you plan to create/modify and why.
   Wait for developer confirmation before proceeding.
4. Implement only the confirmed, scoped task.
5. If schema changes are involved, generate the Alembic migration and stop — do not run
   it against anything but a confirmed local database.
6. Report back exactly which files changed, for developer review before merge.
7. Do not update `STATUS.md` yourself unless asked — the developer will confirm the
   feature works first, then update it (or ask you to).

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
