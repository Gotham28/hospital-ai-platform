# STATUS.md — Current Sprint Status

Last updated: 2026-08-09

This file tracks what's actually done vs. in progress vs. next, across the whole
project. Update this after every verified feature — not before. See `docs/MASTER_PLAN.md`
for full specs, `.agents/AGENTS.md` for permanent rules.

The "Catch-up" section is an append-only log — once an entry is added, do not edit or delete it in later sessions, even if it becomes outdated; add a new dated entry instead. This is the project's running memory of what was actually done, session to session.

---

## IRIS Rheumatology Clinic Features (MASTER_PLAN.md §1.6)

| Feature | Backend | Frontend | Verified working? |
|---|---|---|---|
| 1. Welcome message | ✅ Done | ✅ Done | ✅ Yes |
| 2. Post-booking disclaimer | ✅ Done | ✅ Done | ✅ Yes |
| 3. Outsourced lab test flag | ✅ Done | ✅ Done | ✅ Yes — toggle/note/badge/clear verified across multiple local hospitals. The `PATCH`/`DELETE /lab-tests/{id}` cross-tenant gap noted 2026-08-08 was closed 2026-08-12 (PR #3) |
| 4. Relevance gate before booking | ✅ Done (migration applied) | ✅ Done | ✅ Yes — End-to-end verified with LLM intent constraints |
| 5. Handwritten-record context | 🚫 Deferred — do not build | 🚫 Deferred | — |

**Feature 4 detail (updated 2026-07-22):** Backend implemented (services/relevance.py, ai.py) and migration applied to local DB. Frontend admin UI built (Dashboard settings, Appointments click-to-expand badges). Q1 referral detection bug fixed (now uses LLM).
- **Update:** Conducted rigorous local end-to-end verification of the booking flow. Fixed a latent bug in `ai.py` where providing all booking details simultaneously crashed the model due to incorrect `normalised_value` typing. Verified that irrelevant ailments correctly trigger `needs_staff_review=True` in the database.
- **Fully Verified:** Backend, frontend, AND tested end-to-end in both English (scenarios: referral fast-path, no-referral-but-relevant, no-referral-irrelevant-flagged-for-review, no-gate-hospital, second-booking-attempt-reset) and Malayalam (referral fast-path smoke test, real Appointment row confirmed).

## Catch-up: changes made during separate session
- **Relevance Logging PII Fix:** Modified `services/relevance.py` to only log the LLM's `reason` text when `needs_staff_review` is true, preventing routine clinical details from entering standard logs.
- **Migration Applied:** `632d71467bb1` successfully applied to the local `hospital_ai` database. 
- **Frontend Admin UI:** Added `relevance_criteria` to `Dashboard.tsx`. Wired `AppointmentsTab.tsx` to conditionally show a Relevance column. 
- **Design Decision (Click-to-Expand):** The `needs_staff_review` badge in the table uses a click-to-expand popover to reveal the AI's reasoning, rather than a hover state, ensuring staff deliberately action the review.
- **Backend Bug Fix:** The referral keyword-matching bug in `ai.py` was replaced with a dedicated LLM check (`check_referral_intent`) to accurately parse yes/no/ambiguous answers.
- **Time Import Confirmed:** The `time` module is correctly imported in `ai.py`.

### Catch-up — 2026-08-09
Neon migration (staging) — COMPLETE. Dump/restore executed and fully verified: row
counts (3b), per-hospital parity (3c), cross-tenant referential integrity (3d),
embedding dimensions (3e), and alembic head (3f) all matched between Render and Neon.
DATABASE_URL cutover live; both read-only and write-path smoke tests passed against
the deployed app. Confirmed the app runs correctly against Neon BEFORE the
Render Postgres instance was deleted on 2026-08-09. Traffic-observation gating was
consciously skipped — the app has no real users yet pending Twilio business
registration (separate future task); risk accepted rather than blocked on. Pre-
migration backup retained at D:\Hospital\neon-migration-dump\arogya_staging_render.dump
(single local copy — not yet duplicated to a second location).

**Bonus (unplanned, found/fixed during Feature 3 work):**
- Fixed pre-existing bug in `/chat` (broken since 2026-06-28, commit `da12385`) —
  was 500ing on every request. Fixed in commit `5c98b09`. `/chat` has zero frontend
  callers; documented as internal-testing-only, not deprecated/removed.
- Corrected stale `frontend/src/themes/README.txt` that pointed new theme developers
  at the wrong (non-streaming) endpoint.
- Fixed whole-app "zoomed out" UI issue via `html { font-size: 112.5%; }` in `index.css`.
- Seeded richer local fake data (multiple test hospitals, lab tests, pharmacy items)
  and a local-only superadmin account, for realistic cross-tenant testing going forward.

### Catch-up — 2026-08-12
**Tenant-ownership enforcement on six mutation endpoints — COMPLETE (PR #3, branch `fix/tenant-ownership-mutation-endpoints`, commits `dedd052`, `9915c7f`, `f7dca57`, `a5c9c23`).** Closes the 2026-08-08 audit finding. Endpoints fixed: `PATCH`/`DELETE /knowledge/entry/{id}` (previously unauthenticated entirely), `PATCH`/`DELETE /lab-tests/{id}`, `PATCH`/`DELETE /medicines/{id}`. All six now follow the `approve_appointment` pattern — fetch row, reject when the caller's hospital does not match `hospital_id`, superadmin exempt. Verified with real `/auth/login` tokens against local fixtures: 401 unauthenticated, 403 cross-tenant, 200 owner, 200 superadmin bypass, 404 preserved for missing rows, on each of the six.

Known and deferred: these endpoints return 403 for a row owned by another tenant and 404 for a row that does not exist, which is an enumeration oracle. Deferred deliberately — needs a separate task normalising the response across all seven ownership-checked endpoints.

### Catch-up — 2026-08-13
**Bulk-upload endpoint tenant-ownership enforcement — VERIFIED (branch `fix/bulk-upload-tenant-auth`,
code change uncommitted, awaiting PR).** `POST /hospitals/{hospital_id}/doctors/bulk-upload`
(`hospitals.py` ~line 197) now requires authentication and enforces hospital-ownership, following
the `approve_appointment` pattern. Auth dependency: `get_current_tenant` + `get_token_payload` added
to the route. Ownership check placed after the 404 hospital-existence guard and before `file.read()`.

All five verification cases evidenced against local fixtures:
- (a) No Authorization header, hospital_id=1 → **401**, 0 rows created
- (b) admin1@local.test (hospital 1) posting to hospital 2 → **403**, 0 rows created
- (c) admin1@local.test posting to own hospital 1 → **200**, 3 rows created under hospital 1, no other hospital changed
- (d) superadmin posting to hospital 2 → **200** (auth gate passed correctly); write itself returned 0 rows due to a pre-existing, non-deterministic LLM header-mapping issue unrelated to auth — see Open Questions
- (e) admin token, nonexistent hospital 99999 → **404**, not 403 — confirms existence check still fires before the ownership check

Baseline doctor counts before this session's tests: hospital 1=25, hospital 2=6, hospital 15=2.
After: hospital 1=28 (+3 from case c), hospital 2=6 (unchanged), hospital 15=2 (unchanged).

---

## Phase 1 — Product Improvements (MASTER_PLAN.md §2)

| Item | Status |
|---|---|
| 1.1 Patient Personalisation | ✅ Done (per master plan) |
| 1.2 Extract services out of ai.py | ✅ Done — all 5 stages complete (see detail below) |
| 1.3 Sarvam translation upgrade | ⬜ Not started |
| 1.4 Security hardening | ⬜ Not started |
| 1.5 Multi-tenant isolation hardening | ⬜ Not started |

**§1.2 Service extraction detail (completed 2026-08-07):**
`ai.py` has been split into 5 dedicated service modules across 5 commits:
- Stage 1 (`271745c`): `services/security.py` — `detect_prompt_injection()`, `_INJECTION_PATTERNS`
- Stage 2 (`0301795`): `services/translation.py` — `_translate()`, `_translate_async()` (Google Translate bridge; note for Sarvam upgrade: this is the file to modify for §1.3)
- Stage 3 (`6910e23`): `services/vocabulary.py` + `services/patient_context.py` — vocabulary helpers and Redis-backed session context
- Stage 4 (`aa99831`): `services/rag.py` — all RAG/context-building: `build_context()`, `build_doctor_context()`, `build_kb_context()`, `build_system_prompt_*()`, `build_fallback_instruction()`, PDF/ingest helpers
- Stage 5 (`a53a63a`): `services/booking.py` — booking state machine and session logic

`ai.py` now delegates to these modules. No behavior changes, no signature changes. All `hospital_id` filters preserved in extracted code.

---

## WhatsApp Integration (unplanned — added 2026-08-07)(But currently not in use)

A Twilio-backed WhatsApp messaging feature has been added outside the original plan:

- **`services/whatsapp.py`**: `send_whatsapp_message()` — sends via Twilio, stores a masked-phone log (no raw number stored), records `status`/`twilio_sid`/`error_message`. Tenant-scoped.
- **`models/whatsapp_log.py`**: `WhatsAppLog` table — `hospital_id`, `masked_phone`, `status`, `twilio_sid`, `created_at`.
- **Migration `0c682ef81de1`**: `add_whatsapp_logs_table` applied to local DB.
- **`Multi-Hospital-WhatsApp-Patient-Messaging-Platform/`** (moved out 2026-08-09): a
  standalone Node.js/Express project (SQLite + Twilio) by a separate developer, used to
  send bot links to patients over WhatsApp. It previously sat inside this workspace as a
  nested git repo; it now lives outside the AROGYA repo and is maintained separately. Not
  imported by `backend/app/`, not part of the FastAPI system, and out of scope for all
  AROGYA tasks.
- **Credentials required**: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER` in config. Gracefully degrades if not set.
- **Verified locally**: Migration applied, PII masking confirmed.

---

## Phase 2 — Research (MASTER_PLAN.md §4, later)

Not started. Do not begin until Phase 1 is complete and demoed end-to-end.

---

## Notes / Open Questions for Developer

- Feature 2 disclaimer wording and Feature 3 outsourced-note wording are both still
  pending sign-off from Iris Rheumatology Clinic administration — fields are live and
  configurable but intentionally left empty.
- Feature 4 relevance criteria are partial (referral + prior-doctor checks only) —
  clinic will provide more later; this is expected, not a bug.
- **Next up for Phase 1:** §1.3 Sarvam translation upgrade (modify `services/translation.py`), then §1.4 security hardening (Malayalam injection patterns + `SecurityLog` table), then §1.5 multi-tenant isolation hardening. See MASTER_PLAN.md §2 for specs.
- WhatsApp integration: confirm whether end-to-end testing against Twilio sandbox has been done, and whether it needs a frontend UI surface in the admin panel.
- **Tenant-isolation audit (2026-08-08) — RESOLVED 2026-08-12 via PR #3.** Six endpoints in
  `backend/app/` fetched tenant-owned rows by primary key and mutated them without any
  `hospital_id` check, violating AGENTS.md §5.1 and §4. All six now enforce ownership as of
  PR #3; the endpoint table below is retained for history. Fed into §1.5 multi-tenant
  isolation hardening.

  | Endpoint | File:line | Issue |
  |---|---|---|
  | `PATCH /knowledge/entry/{id}` | `ai.py:1127` | No auth dependency at all; no `hospital_id` filter |
  | `DELETE /knowledge/entry/{id}` | `ai.py:1143` | No auth dependency at all; no `hospital_id` filter |
  | `DELETE /lab-tests/{id}` | `lab_tests.py:42` | `_tenant` injected via `get_current_tenant` but never compared to `db_item.hospital_id` |
  | `PATCH /lab-tests/{id}` | `lab_tests.py:142` | Same |
  | `DELETE /medicines/{id}` | `medicines.py:42` | Same |
  | `PATCH /medicines/{id}` | `medicines.py:148` | Same |

  The two `/knowledge/entry/` routes are the most severe: their only dependency is
  `get_db`, so they are unauthenticated write access to any tenant's `KnowledgeBase` —
  a RAG-corpus integrity risk, not only a data-leak risk.

  Correct pattern already exists in the codebase: `approve_appointment`
  (`appointments.py:190`) fetches the row, then rejects when
  `str(user_hospital) != str(appt.hospital_id)` unless the caller is superadmin. That same check was applied to all six endpoints in PR #3.

  Audit scope caveat: only `.query(<Model>)` call sites were checked. Other access paths
  (raw SQL, CRUD helpers, bulk-upload routes) were not swept and may share the gap.

- **JWT fallback secret (2026-08-08):** `deps.py:10` reads
  `SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-key-change-in-production")`. Any
  environment where `JWT_SECRET` is unset silently accepts tokens signed with a
  publicly-known key. Confirm `JWT_SECRET` is set in every deployed environment —
  worth re-checking during the Neon `DATABASE_URL` cutover, when env vars are being
  edited.

- **Repo hygiene (resolved 2026-08-09):** the stale `.agents/agents_md_review_routing.md`
  duplicate was deleted, `.repomixignore` was added, and the
  `Multi-Hospital-WhatsApp-Patient-Messaging-Platform/` project was moved out of the
  AROGYA repo. The repomix snapshot no longer carries vendored pgvector source, nested
  `.git` internals, or scratch diff files.

- 2026-08-11: Neon migration backup is a single local copy only, not yet duplicated.
  Needs a second encrypted location + checksum + retention owner before the migration is
  considered fully closed.

- **Bulk-upload endpoint unauthenticated (found 2026-08-12, not fixed) — RESOLVED 2026-08-13, see
  Catch-up entry above. Fix on branch fix/bulk-upload-tenant-auth, verified, pending PR/merge.** `POST /hospitals/{hospital_id}/doctors/bulk-upload` (`hospitals.py` ~line 197) has no auth dependency at all and creates `Doctor` rows for whatever `hospital_id` is in the path. Same defect class as the `/knowledge/entry/` routes closed in PR #3, but not covered by the 2026-08-08 audit because that sweep only checked `.query(<Model>)` call sites. Fix implemented and verified locally; PR pending.

- **Bulk-upload endpoint 403/404 behaviour (2026-08-13):** `POST /hospitals/{hospital_id}/doctors/bulk-upload`
  returns 404 for a nonexistent hospital_id and 403 for a valid hospital owned by another tenant —
  joins the existing deferred enumeration-oracle set from PR #3. Needs a separate normalisation
  task across all ownership-checked endpoints.

- **Unaudited bulk-upload siblings (found 2026-08-13):** `POST /lab-tests/hospital/{hospital_id}/bulk-upload`
  (`lab_tests.py:60`) and `POST /medicines/hospital/{hospital_id}/bulk-upload` (`medicines.py:60`)
  have not been checked for auth or tenant ownership — same defect class as this endpoint before
  the fix; PR #3 covered only PATCH/DELETE in those files. Separate task per §5.8.

- **Superadmin bulk-upload "0 doctors" anomaly (2026-08-13):** the LLM header-mapping call
  (GPT-4o-mini, non-deterministic) can return a null column mapping and silently skip every row.
  Confirmed unrelated to auth — the 200 status confirms the ownership gate passed correctly in
  both an occurrence and a non-occurrence of this bug across separate test runs. Pre-existing
  fragility in `bulk_upload_and_sync`'s LLM-based CSV mapping step, not introduced by this fix,
  out of scope here.

- **15 test-artifact Doctor rows identified and removed (2026-08-13):** ids 24–38 in the local
  `doctors` table (`Test8171A/B/C`, `Test8876A/B/C`, `Zeta/Ypsilon/Xi` ×2, `Delta/Echo/Foxtrot`)
  were confirmed via the `H{hospital_id}-D-{hex}` `doctor_id` pattern to be artifacts of prior
  unlogged test sessions verifying this same endpoint — three independent successful writes, each
  correctly scoped to its target hospital_id with no cross-tenant bleed. Deleted by the developer
  to restore a clean fixture baseline ahead of Phase 2 (`tenant_isolation_test.py`, retrieval/LLM
  benchmarks).