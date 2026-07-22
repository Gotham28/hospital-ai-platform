# STATUS.md — Current Sprint Status

Last updated: 2026-07-21

This file tracks what's actually done vs. in progress vs. next, across the whole
project. Update this after every verified feature — not before. See `docs/MASTER_PLAN.md`
for full specs, `AGENTS.md` for permanent rules.

---

## IRIS Rheumatology Clinic Features (MASTER_PLAN.md §1.6)

| Feature | Backend | Frontend | Verified working? |
|---|---|---|---|
| 1. Welcome message | ✅ Done | ✅ Done | ✅ Yes |
| 2. Post-booking disclaimer | ✅ Done | ✅ Done | ✅ Yes |
| 3. Outsourced lab test flag | ✅ Done | ✅ Done | ✅ Yes — toggle/note/badge/clear verified across multiple local hospitals, isolation confirmed |
| 4. Relevance gate before booking | ✅ Done (migration applied) | ✅ Done | ✅ Yes — End-to-end verified with LLM intent constraints |
| 5. Handwritten-record context | 🚫 Deferred — do not build | 🚫 Deferred | — |

**Feature 4 detail (updated 2026-07-22):** Backend implemented (services/relevance.py, ai.py) and migration applied to local DB. Frontend admin UI built (Dashboard settings, Appointments click-to-expand badges). Q1 referral detection bug fixed (now uses LLM).
- **Update:** Conducted rigorous local end-to-end verification of the booking flow. Fixed a latent bug in `ai.py` where providing all booking details simultaneously crashed the model due to incorrect `normalised_value` typing. Verified that irrelevant ailments correctly trigger `needs_staff_review=True` in the database.

## Catch-up: changes made during separate session
- **Relevance Logging PII Fix:** Modified `services/relevance.py` to only log the LLM's `reason` text when `needs_staff_review` is true, preventing routine clinical details from entering standard logs.
- **Migration Applied:** `632d71467bb1` successfully applied to the local `hospital_ai` database. 
- **Frontend Admin UI:** Added `relevance_criteria` to `Dashboard.tsx`. Wired `AppointmentsTab.tsx` to conditionally show a Relevance column. 
- **Design Decision (Click-to-Expand):** The `needs_staff_review` badge in the table uses a click-to-expand popover to reveal the AI's reasoning, rather than a hover state, ensuring staff deliberately action the review.
- **Backend Bug Fix:** The referral keyword-matching bug in `ai.py` was replaced with a dedicated LLM check (`check_referral_intent`) to accurately parse yes/no/ambiguous answers.
- **Time Import Confirmed:** The `time` module is correctly imported in `ai.py`.

**Bonus (unplanned, found/fixed during Feature 3 work):**
- Fixed pre-existing bug in `/chat` (broken since 2026-06-28, commit `da12385`) —
  was 500ing on every request. Fixed in commit `5c98b09`. `/chat` has zero frontend
  callers; documented as internal-testing-only, not deprecated/removed.
- Corrected stale `frontend/src/themes/README.txt` that pointed new theme developers
  at the wrong (non-streaming) endpoint.
- Fixed whole-app "zoomed out" UI issue via `html { font-size: 112.5%; }` in `index.css`.
- Seeded richer local fake data (multiple test hospitals, lab tests, pharmacy items)
  and a local-only superadmin account, for realistic cross-tenant testing going forward.

---

## Phase 1 — Product Improvements (MASTER_PLAN.md §2)

| Item | Status |
|---|---|
| 1.1 Patient Personalisation | ✅ Done (per master plan) |
| 1.2 Extract services out of ai.py | ⬜ Not started — do after IRIS features 3 & 4 |
| 1.3 Sarvam translation upgrade | ⬜ Not started |
| 1.4 Security hardening | ⬜ Not started |
| 1.5 Multi-tenant isolation hardening | ⬜ Not started |

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