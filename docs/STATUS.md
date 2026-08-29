# STATUS.md — Current Sprint Status

Last updated: 2026-08-22

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

* 2026-08-13: Installed the Superpowers plugin (obra/superpowers) in Antigravity and added
  AGENTS.md §11 ("Superpowers Plugin Precedence") to make AGENTS.md §5/§6 override the
  plugin's default mandatory-workflow behavior — specifically one-feature-per-diff,
  confirm-before-code, migration draft-only, and no autonomous merge/PR.

### Catch-up — 2026-08-16

**Bulk-upload sibling endpoints audit and existence guard.** `POST /lab-tests/hospital/{hospital_id}/bulk-upload` and `POST /medicines/hospital/{hospital_id}/bulk-upload` were audited for tenant-ownership enforcement. Added a `404 Not Found` existence guard for non-existent hospitals prior to the ownership check to match the doctors endpoint. 

*Correction:* The 2026-08-13 note about "unaudited bulk-upload siblings" described endpoints that were unverified, not unprotected. The auth and ownership checks were already functionally intact.

Verification tests used `TestClient` against the in-process ASGI app (not a live uvicorn server). Unlike earlier runs which used programmatically minted tokens, these final runs successfully utilized tokens retrieved via the real `POST /api/v1/auth/login` endpoint.

Outcomes demonstrated per endpoint and per case:
**Lab-tests:**
- (a) Unauthenticated → **401 Unauthorized**. Shows auth enforcement.
- (b) Cross-tenant admin → **403 Forbidden**. Shows tenant boundary enforcement.
- (c) Own-hospital admin → **200 OK**, with 3 rows created. Shows that a valid admin can write to their own hospital's data. (Note: This resulted in 0 rows imported across 10 consecutive attempts in the earlier minted-token run, then a 3-row import on the first attempt in the login-token run).
- (d) Superadmin cross-tenant → **200 OK**, with 3 rows created. Shows that a superadmin can write to another tenant's data. (Note: A previous run yielded a 200 with 0 rows imported, which confirmed auth bypassing but failed the write due to LLM variance. The re-run succeeded in proving the write. The mapping is non-deterministic and can return a null mapping, silently importing 0 rows while returning 200; the write succeeds whenever the mapping succeeds.)
- (e) Nonexistent hospital 99999 → **404 Not Found**. Shows existence check enforcement.

**Medicines:**
- (a) Unauthenticated → **401 Unauthorized**. Shows auth enforcement.
- (b) Cross-tenant admin → **403 Forbidden**. Shows tenant boundary enforcement.
- (c) Own-hospital admin → **200 OK**, with 3 rows created. Shows that a valid admin can write to their own hospital's data.
- (d) Superadmin cross-tenant → **200 OK**, with 3 rows created. Shows that a superadmin can write to another tenant's data.
- (e) Nonexistent hospital 99999 → **404 Not Found**. Shows existence check enforcement.

### Catch-up — 2026-08-22

**Five merged PRs recorded in one entry.** STATUS.md had not been updated since
2026-08-09 and the Catch-up log had no entry for any of the following.

- **PR #5** — `fix/bulk-upload-tenant-auth`, commit `c4c4096`, merged `d9e6a78` on
  2026-08-13. Tenant-ownership enforcement on
  `POST /hospitals/{hospital_id}/doctors/bulk-upload`. Verification evidence is in the
  2026-08-13 Catch-up entry above; this entry records only that it merged.
- **PR #6** — `fix/bulk-upload-sibling-guards`, commits `91cb3f7`, `d42dfa8`, merged
  `452ddc3` on 2026-08-15. Hospital-existence guard added to the lab-tests and medicines
  bulk-upload endpoints. Verification evidence is in the 2026-08-16 Catch-up entry above.
- **PR #7** — `docs/agents-close-out-workflow`, commits `28b1a6a`, `7742a29`, `2ba7f59`,
  merged `52cfa4b` on 2026-08-15. Added AGENTS.md §11 (Superpowers Plugin Precedence) and
  §6.11 (task close-out). Two further commits on that branch, `9193ddb` and `1fca2c8`,
  were never pushed and so did not survive the squash merge — recovered by PR #9 below.
- **PR #8** — `docs/research-plan-corrections-2026-08-19`, commits `c291445`, `3604ed8`,
  merged `79cb7b9` on 2026-08-22. Completed the 2026-08-19 translation-baseline
  correction (mBERT/XLM-R replaced by IndicTrans2 / NLLB-200 / mBART-50 at all four
  occurrences), added the Δ = score_EN − score_ML headline metric convention, expanded
  §3.6 into three named leak paths, and added §3.9 `relevance_gate_eval.py`.
  CodeRabbit raised three findings: MD022 was fixed; the §5.8 scope flag was overridden
  knowingly and answered in the PR thread; the metric-notation finding was declined —
  `.coderabbit.yaml` contains no such path instruction and CodeRabbit was quoting the
  PR description back at itself.
- **PR #9** — `chore/gitignore-runs-and-pgvector`, commit `20c7d44`, merged `4e483da` on
  2026-08-22. Added `.agents/runs/` and `backend/pgvector/` to `.gitignore`. These two
  lines were committed locally on the PR #7 branch but never pushed. Without them
  `loop.py` hard-halts at its gitignore check, and its `capture_diff()` runs
  `git add -A -N`, which would sweep run transcripts and vendored pgvector source into
  the review diff.

Documentation only. No code, schema, or migration touched by this entry's work beyond
what the linked PRs already record.

### Catch-up — 2026-08-23

**Task B1 — Malayalam output normaliser module + test script — COMPLETE
(branch `feat/ml-postprocess-normaliser`, PR #11, commit `837001b`).**

Two new files, neither wired into any production call path:

- `backend/app/services/ml_postprocess.py` — pure text-in/text-out
  `normalise_malayalam(text: str) -> str`. Standard library only. No logging of any kind
  (AGENTS.md §5.6 — this handles patient-facing text). No network, DB, Redis or config
  read. Early return leaves text containing no Malayalam codepoint byte-identical.
  `_RULES` holds exactly the three Tier 1 rules from `.agents/CURRENT_TASK.md`:
  (1) chillu normalisation — five consonant+virama+ZWJ sequences mapped to their atomic
  chillu codepoints, runs first; (2) "ഡോ." + whitespace to "ഡോക്ടർ"; (3) word-boundary
  "Dr"/"Dr." to "ഡോക്ടർ". Idempotent. Latin-script doctor NAMES are deliberately not
  transliterated — "Dr. Priya" becomes "ഡോക്ടർ Priya", not "ഡോക്ടർ പ്രിയ".
- `backend/run_ml_postprocess_test.py` — standalone runnable script, no pytest, matching
  the existing `run_e2e_test.py` / `run_malayalam_test.py` convention (AGENTS.md §8).

Verification:

```text
$ python backend/run_ml_postprocess_test.py
PASS rule_1_chillu_normalisation
PASS rule_2_abbreviated_title
PASS rule_3_untranslated_latin_title
PASS rule_3_no_match_inside_word
PASS empty_and_whitespace
PASS empty_string
PASS english_passthrough
PASS no_rules_match
PASS rule_1_chillu_ra
PASS rule_1_chillu_na
PASS rule_1_chillu_la
PASS rule_1_chillu_lla
PASS rule_1_chillu_nna
PASS idempotent_rule_1_chillu_normalisation
PASS idempotent_rule_2_abbreviated_title
PASS idempotent_rule_3_untranslated_latin_title
PASS idempotent_rule_3_no_match_inside_word
PASS idempotent_empty_and_whitespace
PASS idempotent_empty_string
PASS idempotent_english_passthrough
PASS idempotent_no_rules_match
PASS idempotent_rule_1_chillu_ra
PASS idempotent_rule_1_chillu_na
PASS idempotent_rule_1_chillu_la
PASS idempotent_rule_1_chillu_lla
PASS idempotent_rule_1_chillu_nna

26 passed, 0 failed
EXIT CODE: 0
```

Codepoint audit (developer): every ഡോക്ടർ in both files ends U+0D7C (atomic chillu). The
only U+200D in either file is inside Rule 1's test INPUT string, where it belongs. Every
Malayalam string in the test script was read and confirmed by the developer — a test the
agent wrote to match code the agent wrote proves nothing on its own.

Review: via `loop.py`, Sonnet/high, verdict "accept as-is". Two Minor findings, both
resolved before close-out (name placeholder filled; manual steps completed).

Deliberately deferred:

- Wiring is Task B1b, a separate diff per §5.8. Scope already mapped: `_translate_async`
  is called at five points, all in `backend/app/api/v1/endpoints/ai.py`; only three are
  English to Malayalam — lines 227 (greeting), 516 (reply), 918 (error message). Lines
  369 and 413 are Malayalam to English and need no post-processing.
- Formal-pronoun rewriting (§1.3) split out entirely. A blind അവൻ to അദ്ദേഹം swap would
  address a patient's son in the register reserved for a senior physician. It needs a
  context-conditional rule, which does not fit the flat (pattern, replacement) shape.
- Per-hospital configurability dropped 2026-08-22: it would need a Hospital column and an
  Alembic migration, triggering AGENTS.md §10 Opus and ruling out route C.

**Sarvam model finding (2026-08-23) — use `sarvam-translate:v1`, NOT `mayura:v1`.**

`mayura:v1` inverts availability wording in short sentences. "Dr. Priya is available
today" came back as ഡോ. പ്രിയയ്ക്ക് ഇന്ന് സമയം ലഭിക്കുന്നില്ല — "has no time available". The same
inversion occurred with "Doctor" spelled out and with "Dr. Smith". Setting `mode: "formal"`
did not fix it. Worse: positive and negative inputs both render ലഭ്യമല്ല, so the two are
indistinguishable in the output. `sarvam-translate:v1` handled every one of the same
inputs correctly and kept ലഭ്യമാണ് and ലഭ്യമല്ല distinct. Cause: mayura is the colloquial
model, sarvam-translate the formal one. Register differs too — "Please" came back as
ഒന്ന് (casual) from mayura, versus ദയവായി.

- Consequence for §1.3a Task A: use `sarvam-translate:v1`. Its input cap is 2000
  characters, not 1000, which changes Task A's chunking. It is formal-mode-only and may
  reject `mode` / `output_script` — untested.
- Consequence for Task B1b: `sarvam-translate:v1` emits ഡോക്ടർ with U+0D7C directly and
  triggered none of the three rules across 11 probes. The normaliser still stands as
  provider-agnostic defence for the untested Google fallback and for patient-typed input,
  but it has no demonstrated Sarvam trigger. Revisit before wiring.

**`_translate_async()` returns untranslated English on upstream failure (found
2026-08-22, NOT fixed).** Google's free endpoint returned HTTP 429. `translation.py`
lines 41-43 catch the exception, call
`logger.warning("Async translation failed (%s->%s): %s", ...)`, and return the input text
unchanged. The failure IS logged — but no exception is raised and the return value is an
ordinary string, so the caller in `ai.py` cannot tell an untranslated reply from a
translated one, and a Malayalam-speaking patient receives English. `_translate()` lines
26-28 behave identically. Corrected 2026-08-23: this bullet originally claimed no error
was recorded anywhere, which CodeRabbit correctly flagged on PR #11 — the failure is
logged, it is simply invisible to the caller. Not fixed here — out of scope for B1 per
§5.8. Feeds the §1.3a Task A circuit breaker.

**Patient text can reach the application log on translation failure (found 2026-08-23,
NOT fixed).** Following that exception into the log line: `resp.raise_for_status()` raises
`httpx.HTTPStatusError`, whose message is built from the template
`"{error_type} '{0.status_code} {0.reason_phrase}' for url '{0.url}'"` — verified against
`httpx.Response.raise_for_status` source on 2026-08-24. `{0.url}` is the full request URL,
and `translation.py` lines 21 and 35 place the text being translated into that URL as the
`q=` parameter. Passing the exception object into `logger.warning` therefore writes that
text into the log. For an English→Malayalam call it is AROGYA's own outgoing reply; for
the Malayalam→English calls at `ai.py` lines 369 and 413 it is the patient's own typed
message. This contradicts AGENTS.md §5.6. Pre-existing — introduced with `translation.py`
at §1.2 Stage 2 (commit `0301795`), not by Task B1 — and deliberately not fixed here per
§5.8 and the `CURRENT_TASK.md` "Do NOT touch" list. No real patient traffic yet (Twilio
business registration outstanding, see Catch-up 2026-08-09), so nothing is known to have
leaked.

### Catch-up — 2026-08-27

**Raw patient text removed from application logging — COMPLETE
(branch `fix/remove-patient-text-from-logs`, PR #TBD).**

Six log sites across four files. Closes the two §5.6 findings recorded in
Catch-up 2026-08-23.

- `backend/app/main.py` — `logging.getLogger("httpx").setLevel(logging.WARNING)`
  added after `logging.basicConfig`. httpx logged every request at INFO with the
  full URL, and `translation.py` places the text being translated in that URL as
  the `q=` parameter, so this fired on every successful translate call, not only
  on failure.
- `backend/app/services/translation.py` — both `except` blocks now log
  `type(e).__name__`, plus `e.response.status_code` when the exception is an
  `httpx.HTTPStatusError`. The exception object itself is never passed to the
  logger. `source` and `target` retained.
- `backend/app/api/v1/endpoints/ai.py` lines 414 and 437 — patient text replaced
  with `len()`. `intent` retained as a classification label.
- `backend/app/services/relevance.py` line 223 — `patient_answer[:100]` replaced
  with `len(patient_answer)`. `hospital_id` and `parsed_as` retained.

Verified live against the local `hospital_ai` database, port 8000 confirmed free
before starting. One `/chat-stream` request with `language="ml"` and synthetic
Malayalam, sent identically before and after.

BEFORE (13:42) — four leak sites in one request:
- `httpx: HTTP Request: GET ...&q=<text>`
- `Async translation failed (ml->en): ... for url '...q=<text>'`
- `[Translation] ml->en: '<text>' -> '<text>'`
- `[Intent] <text> -> OTHER`

AFTER (13:45) — same request:
- httpx GET line absent
- `Async translation failed (ml->en): HTTPStatusError (status=429)`
- `[Translation] ml->en: len=33 -> len=33`
- `[Intent] len=33 -> OTHER`

Forced failure, `_translate("APPOINTMENT TEST TEXT", "en", "zz-not-a-language")`:
- before: `Client error '429 Too Many Requests' for url '...q=APPOINTMENT+TEST+TEXT'`
- after: `HTTPStatusError (status=429)`

Referral path: `[Relevance] hospital_id=1 referral check answer_len=54
parsed_as=True`.

No Alembic command run, no migration file created. All test text synthetic.

Out of scope and untouched: the `_translate_async()` "returns untranslated English
on upstream failure" bug in the same `except` blocks (Task A's circuit breaker,
§5.8); `whatsapp.py` line 65; `ai.py` line 1079; any hashing of logged text
(MASTER_PLAN.md §1.4 owns that). `MASTER_PLAN.md` §9 appended.

### Catch-up — 2026-08-28
**AGENTS.md §12 orchestration rules added; drive skill removed — COMPLETE
(branch `chore/agents-md-s12-orchestration`).**

Added AGENTS.md §12, the Claude Code / Antigravity closed-loop orchestration process
(§12.1–§12.15), and removed the `drive` skill and its unattended runner
(`.claude/skills/drive/`, `.agents/run-unattended.ps1`), which conflicted with §12 in
several ways: it committed and pushed autonomously, it wrote `.agents/handoff.md` in an
incompatible format that collides with §12's own halt file on a case-insensitive
filesystem, its OPUS branch had no resume path, and it emitted its own tier line where
§12.9 reserves escalation-only rights for Claude Code. Also corrected two stale AGENTS.md
entries: the §2 Translation bullet (Task B1's Malayalam normaliser had landed as PR #11
but the file still said "not yet started"), and added a §3 table row for
`backend/app/services/ml_postprocess.py`, which had no entry.

Environment work needed to make this task runnable, done by the developer:
- Granted write permission on the repo tree for a non-elevated shell
  (`icacls ... /grant "$env:USERNAME:(OI)(CI)F" /T`, 61,609 files, 0 failures).
- Discovered and worked around a Windows filename collision: `.agents/HANDOFF.md` and
  `.agents/handoff.md` are the same file, so a halt firing before the task's own
  deletion step overwrote leftover output from PR #15's `drive` run. §12's halt file is
  renamed to `.agents/LOOP_HANDOFF.md` as part of this change specifically to remove the
  collision going forward.
- Fixed `~/.gemini/antigravity-cli/settings.json`, which held two separate top-level
  JSON objects so its permissions block never parsed; added `read_file`/`write_file`
  grants scoped to this repo. No `command(...)` grant was added, deliberately — that
  remains withheld.
- The three scoped deletions (the drive skill directory and its runner, plus the stale
  `.agents/handoff.md`) had to be performed manually by the developer rather than
  through the Antigravity dispatch (`agy`) this task otherwise used for them: `agy` has
  no dedicated delete-file tool, shells out to `rm`/`del` to delete, and that requires
  the `command(...)` permission this task deliberately withholds. This is a known limit
  of the current route D setup, not fixed by this task.

Scope: `.agents/AGENTS.md`, `docs/MASTER_PLAN.md`, `.claude/skills/drive/` (deleted),
`.agents/run-unattended.ps1` (deleted). Related: CURRENT_TASK.md dated 2026-08-28.

---

## Phase 1 — Product Improvements (MASTER_PLAN.md §2)

| Item | Status |
|---|---|
| 1.1 Patient Personalisation | ✅ Done (per master plan) |
| 1.2 Extract services out of ai.py | ✅ Done — all 5 stages complete (see detail below) |
| 1.3 Sarvam translation upgrade | 🟡 In progress — normaliser wired into ai.py (Task B1b); Task A next, Sarvam API key received 2026-08-29 |
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
- **Next up for Phase 1:** §1.3a Task A — Sarvam client + Google fallback with an
  in-process circuit breaker, in `services/translation.py`. **Unblocked: the Sarvam API
  key arrived 2026-08-29.** Then Task C (Redis translation cache, Opus tier). Read
  Catch-up 2026-08-23 before starting Task A: it must use `sarvam-translate:v1`, not
  `mayura:v1`; input cap 2000 characters, not 1000; it is formal-mode-only and may
  reject `mode` / `output_script` — untested.
- **Live rule-firing of `normalise_malayalam()` on a successfully translated Malayalam
  string has never been observed** (Google 429 on all three Task B1b attempts,
  2026-08-29). Deliberately not chased further — folded into §1.3a Task A, which is now
  unblocked. When `sarvam-translate:v1` becomes primary, real translated Malayalam
  passes through `ai.py` lines 228, 517 and 919, and the output should be read then.
  Note the finding already recorded in Catch-up 2026-08-23: `sarvam-translate:v1` emits
  ഡോക്ടർ with U+0D7C directly and triggered none of the three rules across 11 probes, so
  Task A may confirm the wiring without any rule firing either. If so, the Google
  fallback path remains the only place these rules are expected to fire.
- **Stale governing docs after Task B1b and the Sarvam key (2026-08-29, NOT fixed).**
  Three lines are now wrong and none may be edited by the agent layer: AGENTS.md §2's
  Translation bullet says the Malayalam normaliser "has landed but is not yet wired into
  any call path"; AGENTS.md §3's file-table row for
  `backend/app/services/ml_postprocess.py` says "not currently wired into any production
  call path"; and MASTER_PLAN.md §1.3a order item 1 says "Obtain the Sarvam API key
  (developer, not started)". AGENTS.md is read at the start of every session, so a stale
  line there actively misleads future work — the same failure mode corrected on
  2026-08-28. Needs its own small docs task.
- **Suspected pre-existing bug (found 2026-08-29, unconfirmed, NOT fixed) —
  chat-stream's own new-session greeting bypasses translation entirely.**
  `ai.py:442-445`:
```python
          if _turn_ctx.get("_is_new_session"):
              hospital_for_welcome = db.query(Hospital).filter(Hospital.id == request.hospital_id).first()
              if hospital_for_welcome and hospital_for_welcome.welcome_message:
                  yield f"data: {json.dumps(hospital_for_welcome.welcome_message)}\n\n"
```
  This yields `hospital.welcome_message` raw, with no `_translate_async()` or
  `normalise_malayalam()` call at all — unlike `get_welcome()`'s handling of the same
  field (line 228, which Task B1b wired). A patient starting a new session with
  `language="ml"` at a hospital with a custom `welcome_message` set may receive that
  greeting in plain English via `/chat-stream`, even though the same greeting is
  correctly translated when served via `GET /welcome/{hospital_id}`. Pre-existing (not
  introduced by Task B1b), unconfirmed (no hospital in the local DB has a
  `welcome_message` set, so this has not been observed live), and deliberately not fixed
  here — out of scope under §5.8.
- **`mayura:v1` is unusable for AROGYA (2026-08-23):** it inverts availability wording
  and renders positive and negative identically. Task A must use `sarvam-translate:v1`,
  cap 2000 chars. Full detail in Catch-up 2026-08-23.
- **`_translate_async()` returns untranslated English on upstream failure (2026-08-22,
  not fixed):** confirmed against a Google HTTP 429. The failure IS logged via
  `logger.warning` (`translation.py` lines 41-43), but no exception is raised, so the
  caller cannot distinguish failure from success. Same in `_translate()` lines 26-28.
  To be fixed by the Task A circuit breaker. Detail in Catch-up 2026-08-23.
- **Docs-hygiene follow-up task queued (2026-08-23), deliberately NOT bundled into Task
  B1 per §5.8:** (i) AGENTS.md §2 still says the Sarvam upgrade is "not yet started";
  (ii) AGENTS.md §3 file table does not list `backend/app/services/ml_postprocess.py`;
  (iii) the Repo Hygiene bullet is marked RESOLVED while still saying `.repomixignore`
  needs confirming (CodeRabbit finding merged over); (iv) six RESOLVED bullets in this
  section should collapse to one-liners pointing at their Catch-up entries.
  Swept and confirmed NOT stale on 2026-08-23: MASTER_PLAN.md §1.3a names neither
  `mayura:v1` nor a 1000-character input cap.
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
  Catch-up entry above. Fix on branch fix/bulk-upload-tenant-auth, merged 2026-08-13 as PR #5.** `POST /hospitals/{hospital_id}/doctors/bulk-upload` (`hospitals.py` ~line 197) has no auth dependency at all and creates `Doctor` rows for whatever `hospital_id` is in the path. Same defect class as the `/knowledge/entry/` routes closed in PR #3, but not covered by the 2026-08-08 audit because that sweep only checked `.query(<Model>)` call sites. Fix implemented, verified locally, and merged as PR #5.

- **Bulk-upload endpoint 403/404 behaviour (2026-08-13):** `POST /hospitals/{hospital_id}/doctors/bulk-upload`
  returns 404 for a nonexistent hospital_id and 403 for a valid hospital owned by another tenant —
  joins the existing deferred enumeration-oracle set from PR #3. Needs a separate normalisation
  task across all ownership-checked endpoints.

- **Unaudited bulk-upload siblings (found 2026-08-13) — RESOLVED 2026-08-16 via PR #6.** `POST /lab-tests/hospital/{hospital_id}/bulk-upload`
  (`lab_tests.py:60`) and `POST /medicines/hospital/{hospital_id}/bulk-upload` (`medicines.py:60`)
  were flagged as unchecked for auth or tenant ownership; PR #3 had covered only PATCH/DELETE in
  those files. Audited 2026-08-16: both already enforced auth and ownership, and a 404
  hospital-existence guard was added to match the doctors endpoint. See the 2026-08-16 Catch-up entry.

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
- **Repo Hygiene Issue (2026-08-16) — RESOLVED 2026-08-22 via PR #9.** The `backend/pgvector/` directory was appearing as untracked in `git status`, covered by neither `.gitignore` nor `.repomixignore`, reopening the 2026-08-09 hygiene note. `.gitignore` now covers both `backend/pgvector/` and `.agents/runs/` as of PR #9. `.repomixignore` was not changed — confirm separately that the repomix snapshot still excludes vendored pgvector source.
- **Redundant Branch (2026-08-16) — RESOLVED 2026-08-22.** Branch `fix/bulk-upload-tenant-auth` was redundant — its content is already on `origin/main` via PR merge `d9e6a78`. Deleted locally and on the remote on 2026-08-22.

- **Patient text in application logs — RESOLVED 2026-08-27.** Both findings from
  Catch-up 2026-08-23 (the `translation.py` exception-object leak, and the httpx
  INFO-level URL logging) are closed. See Catch-up 2026-08-27.

### Catch-up — 2026-08-29

**Task B1b — normalise_malayalam() wired into ai.py — CODE COMPLETE, live rule-firing
proof not observed.**

Branch: `feat/ml-postprocess-wiring`, cut from `origin/main`.
PR: pending
Commits: pending

Wired the existing Malayalam output normaliser (`ml_postprocess.py`, Task B1, PR #11)
into the three English-to-Malayalam `_translate_async()` call sites in
`backend/app/api/v1/endpoints/ai.py`: the custom hospital welcome-message greeting
(line 228, served by `GET /welcome/{hospital_id}`), the appointment-status reply
(line 517), and the booking-validation error message (line 919). The two
Malayalam-to-English call sites (lines 370, 414) and `ml_postprocess.py` /
`translation.py` themselves were left untouched, per scope. One new import added; no
function signature changed.

Verification: `grep -n "_translate_async("` confirmed 5 call sites (3 en→ml, 2 ml→en)
before any edit. `python backend/run_ml_postprocess_test.py` still 26 passed, 0 failed
after the edit (re-confirmed across three verification rounds). Live `/chat-stream`
smoke tests (hospital_id=1, synthetic questions) confirmed correct, unaffected
Malayalam and English replies on the general-chat path.

**Live test at `ai.py:228`.** With developer-supplied local admin credentials,
temporarily set hospital 1's `welcome_message` (originally `null`) to the synthetic
English string `"Welcome to our clinic. Dr. Priya will see you shortly."` via
`PATCH /hospitals/1`, called the real `GET /welcome/1` endpoint live, and restored the
original `null` value afterward (confirmed by re-read).

The wiring itself rests on inspection of a four-line diff with no conditional branches,
plus the 26 passing unit tests on `normalise_malayalam()` in isolation. The failure
path is verified live: Google Translate returned HTTP 429, the English input came back
unchanged, with no mangling of the "Dr." in the source text. Live rule-firing on a
*successful* English-to-Malayalam translation has never been observed, across three
review rounds and three separate attempts, because Google 429'd on every one. This
round's live result is evidence for the failure path only — it cannot show whether
`normalise_malayalam()` actually ran on that request, because the bytes returned are
identical whether the wrapper executed and no-opped, or was never called at all.

Deliberately deferred, unchanged by this task:
- Formal-pronoun rewriting, per-hospital normalisation config, the `_translate_async()`
  untranslated-on-failure bug, and the Sarvam client itself — all §1.3a Task A, split
  out under §5.8 (one feature per diff). The Sarvam API key arrived 2026-08-29, so
  Task A is no longer blocked.
- **Mixed-script residual case (known, narrow, not fixed):** `ml_postprocess.py:24-25`'s
  guard only early-returns when a string contains *zero* Malayalam codepoints. A
  failure-path string containing at least one Malayalam character (e.g. a
  partially-successful translation) would pass the guard, and Rule 3 could then rewrite
  a literal "Dr." inside the still-English remainder. Not observed live in any of the
  three verification rounds (every 429 this task hit returned a purely English,
  zero-Malayalam-codepoint string), but not structurally impossible. No code change
  made — `ml_postprocess.py` is on the Do NOT touch list for this task.

No Antigravity dispatch ran for this task in any round — all code and verification work
was performed directly by Claude Code — so the §12.9 tier-ratchet had no independent
floor to check against; the classification (Sonnet 5, medium, no Opus trigger) stands
unescalated.

`git status --short` confirms `ai.py` as the only tracked file this task's Agent-layer
work modified (`.agents/CURRENT_TASK.md` also shows modified on this branch, which is
Claude Chat's own governance-file activity per §12.1, not caused by this task's code
work).

