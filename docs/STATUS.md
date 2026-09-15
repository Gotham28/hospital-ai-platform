# STATUS.md — Current Sprint Status

Last updated: 2026-09-01

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
| 1.3 Sarvam translation upgrade | 🟡 In progress — Task B (normaliser, PR #17) and Task A (Sarvam client + Google fallback + circuit breaker, PR #19) both done; Task C (Redis translation cache, Opus tier) remaining |
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

## Phase 2 — Research (MASTER_PLAN.md §3, later)

Not started. Do not begin until Phase 1 is complete and demoed end-to-end.

---

## Notes / Open Questions for Developer

- Feature 2 disclaimer wording and Feature 3 outsourced-note wording are both still
  pending sign-off from Iris Rheumatology Clinic administration — fields are live and
  configurable but intentionally left empty.
- Feature 4 relevance criteria are partial (referral + prior-doctor checks only) —
  clinic will provide more later; this is expected, not a bug.
- **Next up for Phase 1:** §1.3a Task A is done (PR #19, 2026-09-01) — Sarvam client
  is primary, Google fallback, per-provider circuit breaker, in
  `services/translation.py`. **Remaining: Task C (Redis translation cache, Opus
  tier)** — not yet scoped.
- **Live rule-firing of `normalise_malayalam()` on a successfully translated Malayalam
  string has never been observed** (Google 429 on all three Task B1b attempts,
  2026-08-29). Deliberately not chased further — folded into §1.3a Task A, which is now
  unblocked. When `sarvam-translate:v1` becomes primary, real translated Malayalam
  passes through `ai.py` lines 228, 517 and 919, and the output should be read then.
  Note the finding already recorded in Catch-up 2026-08-23: `sarvam-translate:v1` emits
  ഡോക്ടർ with U+0D7C directly and triggered none of the three rules across 11 probes, so
  Task A may confirm the wiring without any rule firing either. If so, the Google
  fallback path remains the only place these rules are expected to fire.
- **Stale governing docs after Task B1b and the Sarvam key (2026-08-29) — RESOLVED
  2026-08-29 by hand.** All three lines corrected directly by the developer, not through
  the agent layer: AGENTS.md §2's Translation bullet and §3's file-table row for
  `backend/app/services/ml_postprocess.py` now record the normaliser as wired (PR #17),
  and MASTER_PLAN.md §1.3a order item 1 now records the Sarvam key as received. §1.3a's
  "close-out for every task above is manual" paragraph was deliberately left unchanged —
  see Catch-up 2026-08-29 (second entry) for why.
- **RESOLVED 2026-09-15 (see Catch-up below) — chat-stream's new-session greeting
  bypassed translation entirely.** Previously recorded here as suspected and
  unconfirmed (found 2026-08-29). Confirmed live via before-evidence
  (`language="ml"`, English-authored `welcome_message`, greeting arrived
  untranslated) and fixed on branch `fix/chat-stream-welcome-translation`.
  While investigating, a second, related gap was found and fixed in the same
  task: `get_welcome()`'s existing translation call (the pattern being
  copied) also assumed `welcome_message` is always English-authored, which
  would garble a Malayalam-authored greeting post-fix. Both call sites now
  share a `contains_malayalam()` guard that skips en→ml translation when the
  source text is already Malayalam. See Catch-up entry below for evidence and
  detail.
- **`mayura:v1` is unusable for AROGYA (2026-08-23):** it inverts availability wording
  and renders positive and negative identically. Task A must use `sarvam-translate:v1`,
  cap 2000 chars. Full detail in Catch-up 2026-08-23.
- **`_translate_async()` returns untranslated English on upstream failure (2026-08-22,
  not fixed):** confirmed against a Google HTTP 429. The failure IS logged via
  `logger.warning` (`translation.py` lines 41-43), but no exception is raised, so the
  caller cannot distinguish failure from success. Same in `_translate()` lines 26-28.
  To be fixed by the Task A circuit breaker. Detail in Catch-up 2026-08-23.
- **Docs-hygiene follow-up task queued (2026-08-23), deliberately NOT bundled into Task
  B1 per §5.8:** (i) AGENTS.md §2 still says the Sarvam upgrade is "not yet started" —
  RESOLVED 2026-08-29; (ii) AGENTS.md §3 file table does not list
  `backend/app/services/ml_postprocess.py` — RESOLVED 2026-08-28; (iii) the Repo Hygiene
  bullet is marked RESOLVED while still saying `.repomixignore` needs confirming
  (CodeRabbit finding merged over) — STILL OPEN; (iv) six RESOLVED bullets in this
  section should collapse to one-liners pointing at their Catch-up entries — STILL OPEN.
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
PR: #17
Commits: 625cf91 (feature); docs commits recording the PR number follow on the same branch

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

### Catch-up — 2026-08-30

**Task A — Sarvam translation client + Google fallback + circuit breaker —
CODE COMPLETE (branch `feat/sarvam-translation-client`).**

Closes MASTER_PLAN.md §1.3a Task A. Three bundled changes, chosen knowingly at
scoping despite §5.8: provider swap, failure-contract change, and chunking.

- `backend/app/services/translation.py` — Sarvam (`sarvam-translate:v1`) is now
  primary, Google's gtx endpoint the fallback. New `TranslationUnavailableError`;
  `_translate()` and `_translate_async()` now raise it when both providers fail
  instead of returning the untranslated input. This closes the bug recorded in
  Catch-up 2026-08-23. Per-provider in-process `_CircuitBreaker` — 3 consecutive
  failures, 60s open, no half-open probe, reset on close. Redis was ruled out at
  scoping because it fires the §10 session-key trigger. Sarvam-only chunking at
  2000 characters on sentence boundaries; 2000 exactly does not chunk. Trailing
  whitespace is stripped before each provider call and re-attached to the
  translated chunk, so seam spacing survives the rejoin. Any chunk failing aborts
  the whole Sarvam attempt and falls to Google with the full original text — no
  partial translation can reach a patient. Google is never chunked.

- `backend/app/api/v1/endpoints/ai.py` — all five `_translate_async()` call sites
  now handle the raise. The three en→ml sites (welcome greeting line 229, STATUS
  reply line 527, booking-validation error line 932) each have a
  `TranslationUnavailableError` branch followed by a broader `except Exception`
  branch, so an unexpected failure from `normalise_malayalam()` cannot kill the
  /chat-stream SSE generator mid-response. The two ml→en sites (lines 373, 422)
  fall back to the untranslated patient question. Every branch logs
  `type(e).__name__` only. No `from e` anywhere — deliberate: `httpx.HTTPStatusError`
  carries the request URL, and `translation.py` puts the text being translated into
  that URL as the `q=` parameter, so chaining would reopen the §5.6 leak closed on
  2026-08-27. Patient sees English on total failure; no new Malayalam string was
  authored, since nobody in the loop can verify Malayalam they wrote themselves.

- `backend/run_translation_test.py` — new standalone script, matching the
  `run_ml_postprocess_test.py` convention. 34 tests: chunk boundaries at
  1999/2000/2001, hard-split termination, seam spacing, breaker open/skip/cooldown,
  provider independence, total-failure raise (sync and async), and key-unset
  skip-to-Google.

- `backend/app/core/config.py` — not touched. `SARVAM_API_KEY` already existed;
  the URL and model live as private constants beside `_GTRANSLATE_URL`.

Live evidence (developer, PowerShell, outside the agent environment — both
`api.sarvam.ai` and `api.openai.com` are unreachable from the agent sandbox, so no
/chat-stream evidence exists for this task):

```text
--- en-IN -> ml-IN --- STATUS: 200
{"translated_text":"ഡോക്ടർ പ്രിയ ഇന്ന് ലഭ്യമാണ്. പതിനഞ്ച് മിനിറ്റ് നേരത്തെ എത്തുക.", ...}
--- ml-IN -> en-IN --- STATUS: 200
{"translated_text":"I need an appointment.", ...}
```

This confirms the two API details the code had guessed: the response field is
`translated_text`, and the language codes are `en-IN` / `ml-IN`. It also confirms
from the opposite direction the Catch-up 2026-08-23 finding — `sarvam-translate:v1`
renders "is available" as ലഭ്യമാണ്, where `mayura:v1` inverted it.

Test evidence: `run_translation_test.py` 34 passed, 0 failed;
`run_ml_postprocess_test.py` 26 passed, 0 failed (unchanged, no regression).

Known and NOT fixed here:
- An all-whitespace chunk would send empty input to Sarvam. Reachable only via a
  >2000-character admin field made mostly of blank lines. Degrades safely — Sarvam
  rejects it, the whole call falls to Google.
- Sarvam transliterates doctor names (`Priya` → `പ്രിയ`) where `normalise_malayalam()`
  deliberately does not. The two providers therefore render names differently. Needs
  its own task.
- `sarvam-translate:v1` emits ഡോക്ടർ with U+0D7C directly, so none of the three
  normaliser rules fire on Sarvam output. The Google fallback remains the only path
  where they are expected to fire — as predicted in Catch-up 2026-08-23.
- `mode` / `output_script` were deliberately omitted from the Sarvam payload; their
  acceptance is untested.
- Branch history note: this work was written on `docs/governing-docs-staleness-2026-08-29`
  and moved to a clean branch cut from `origin/main` before commit, per §6.10.
### Catch-up — 2026-08-29 (second entry)

**Governing-doc staleness corrected by hand — COMPLETE. No agent layer involved.**

Three lines fixed directly by the developer in `.agents/AGENTS.md` and
`docs/MASTER_PLAN.md`:

- AGENTS.md §2 Translation bullet — now records `ml_postprocess.py` as wired into the
  three English-to-Malayalam call sites in `ai.py` (PR #17, merged 2026-08-29), and the
  Sarvam key as received. Deliberately does not name line numbers: the 2026-08-23 numbers
  went stale after the 2026-08-27 log-hygiene edit, which is why Task B1b chose route B
  over route C. A `grep -n "_translate_async("` pointer replaces them.
- AGENTS.md §3 file-table row for `backend/app/services/ml_postprocess.py` — same
  correction.
- MASTER_PLAN.md §1.3a order item 1 — Sarvam key recorded as received 2026-08-29,
  Task A unblocked.

Done by hand rather than through the agent layer for two reasons. First, §12.15's
append-only rule lets the agent layer append to MASTER_PLAN.md §9 and nothing else, so
§1.3a was never the agent's to edit. Second, three line edits do not justify a task file,
branch, review cycle and PR.

**A fourth edit was scoped and then dropped.** The original plan also rewrote §1.3a's
"Close-out for every task above is manual (`close-task`). No loop runner commits, pushes,
opens or merges a PR." paragraph, on the grounds that AGENTS.md §12.10 had superseded it.
That reasoning was wrong on the dates: §6.11 already permitted agent commit/push/PR from
2026-08-15 (PR #7, merge `52cfa4b`), and §1.3a's manual-close-out sentence was written a
week later on 2026-08-22. It was never stale text — it is a deliberate narrowing of a
permission that already existed. Task C (Redis translation cache) is the Opus-tier task
named in MASTER_PLAN.md §3.6 case 2 as a cross-tenant leak path, and its close-out stays
manual. The paragraph is unchanged.

**PR #17 commit-hash discrepancy (recorded, not resolved).** Catch-up 2026-08-29 above
records `Commits: f15d435` for PR #17. A later check of `origin/main` reported the PR as
squash commit `0336e6b`, squashing `625cf91` and `8b7ce52` — `f15d435` appears in neither.
Most likely `f15d435` was the round-one commit and two further verification rounds rewrote
the branch before merge. Not confirmed against `git log`. The earlier entry is left as
written per the append-only rule; this entry is the correction.

### Catch-up — 2026-08-29 (third entry)

**AGENTS.md §12 internal contradictions resolved; close-task skill rewritten.**

Branch: `docs/governing-docs-staleness-2026-08-29`.
PR: #18
Commits: `1aa3d73`, `496cb89`

§12 landed on 2026-08-28 already inconsistent with itself. Four fixes:

- §12.1, Claude Code row — "Never does: Any git write" and "Any edit to
  `docs/STATUS.md`" both removed. §12.10 permits feature-branch git writes and §12.15
  permits writing STATUS.md after approval, so the summary row contradicted two later
  subsections. "Merge a PR, ever" and the `CURRENT_TASK.md` / `DECISION.md` ban were
  pulled up into the cell so it still reads as a real summary.
- §12.1, Claude Chat row — "Touch the repo" now excepts `.agents/CURRENT_TASK.md` and
  `.agents/DECISION.md`, which §12.7 and §12.15 make Claude Chat's files to write.
- §12.2 step 7 — relaxed from "Developer only, per §6.11. Never automated." to Claude
  Code driving close-out on a feature branch, stopping short of merge. §6.11 has
  permitted this since 2026-08-15 (PR #7, `52cfa4b`) and §12.10 since 2026-08-28, so
  the old step 7 contradicted both. Step 7 is now explicitly a floor, not a ceiling: a
  task file or plan section may still narrow close-out to manual, and MASTER_PLAN.md
  §1.3a continues to do exactly that for the three Sarvam tasks.
- §12.9 — new bullet covering the case where no Antigravity dispatch runs. There is
  then no independent tier line to ratchet from, and Claude Code must say so rather
  than presenting its own §10 classification as a second opinion.

**`close-task` skill rewritten. No diff — it is a Claude Project skill, not a repo
file, so nothing about it appears in this commit or any `git log`.** Its §2 had
asserted "Claude Code cannot run git writes, AGENTS.md §12.10 forbids it", true of an
older AGENTS.md and false since 2026-08-28. It therefore routed every git step through
an Antigravity dispatch that cannot run them — `agy` has no `command(...)` grant,
deliberately withheld (see Catch-up 2026-08-28) — so the prompt it produced could not
have executed. Changes: §2 rewritten with §12.10 quoted rather than paraphrased and
Antigravity removed from close-out entirely; new §2c narrowing check; new §5a for
deliverables that produce no diff; §2b sweep extended to cover skills that quote a
rule; §3 gained branch-cutting and explicit-target push; §5 split into an unfiltered
fetch and a verification pass where Claude Code reads each CodeRabbit claim back off
disk and pastes evidence without deciding whether to fix; §6 now triages from that
evidence rather than from a repomix snapshot; new §7 on the §12.9 tier floor.
Description trimmed to 1022 characters to meet the 1024 limit, dropping the trigger
phrases 'wrap this up' and 'raise the PR'.

**Two silent no-ops, caught by the close-out gate.** The §1.3a order item 1 edit was
believed made by hand on 2026-08-29 and was not. `git add` on an unmodified file
succeeds silently, so the first commit on this branch went through describing an edit
it did not contain, and a later `git commit --amend --no-edit` appeared to work while
changing nothing — the amend rewrote `69ca77d` to `1aa3d73` with the same three files.
Both were found by reading the claimed diff back off disk before writing anything,
rather than by trusting a commit message. The edit landed on the third attempt and is
carried by the second commit on this branch. Commit `1aa3d73`'s message still claims a
MASTER_PLAN.md edit it does not contain; left uncorrected rather than amended again.

Verification: no commands run beyond git and one character count. Docs-only change,
plus one file outside the repo. Nothing here was executed or tested, and nothing in it
could be.

Deliberately deferred:
- MASTER_PLAN.md §1.3a's "Close-out for every task above is manual" paragraph stays
  unchanged. See Catch-up 2026-08-29 (second entry) for the dating argument.
- Docs-hygiene items (iii) and (iv) from Catch-up 2026-08-23 are still open.
- No sweep of §11 or §§1–10 for contradictions of the same class. Only §12 was swept.
- Ten untracked files left in place: `.agents/DECISION.md`,
  `.agents/DECISIONS_TAKEN.md`, `.agents/LOOP_HANDOFF.md` from earlier resolved tasks,
  and seven scratch/test scripts. Untracked, so they cannot reach a commit. Cleanup is
  its own task.

### Catch-up — 2026-08-31

**Task 1 of 3 — IRIS design tokens (foundation) — CODE COMPLETE, NOT COMMITTED
(branch `feat/iris-design-tokens`, cut from `origin/main` at `12b7c66`, PR #18).**

Foundation for the IRIS theme rebuild. Two files. No component consumes any new
token yet.

- `frontend/src/index.css` — added the `iris-*` colour and type tokens to the
  `@theme` block. This project is on Tailwind v4: `tailwind.config.js` is not read
  and there is no `@config` directive, so `@theme` in `index.css` is the only place
  a token can be declared. 22 new custom properties: 9 `--color-iris-*`
  (primary #2A69B5, primary-hover #1E4E8C, surface #F7F9FC, surface-raised #FFFFFF,
  border #D5DEE8, text-primary #1C2430, text-muted #5C6875, accent #0E7C86,
  danger #B04A2F), 10 `--text-iris-*` (label/ui/body/body-ml/title, each with a
  `--line-height` companion), `--radius-iris: 16px`, `--shadow-iris: 0 2px 8px
  rgba(28,36,48,0.10)`, and `--font-malayalam` — the one token not
  `iris`-namespaced, carried over verbatim from the developer-approved starting
  block despite the stated namespace rule.
- `frontend/index.html` — added Noto Sans Malayalam to the font link; `<title>`
  changed to "Arogya".

**Verification — DEVELOPER-ATTESTED, NOT EVIDENCED (§5.10 exception, accepted by
the developer 2026-09-01).** The checks below were run during the authoring session
and their raw output was not preserved to any file. They were not re-run for this
entry. Recorded as an attestation, not as evidence: `npm run build` exit 0 with no
Tailwind warnings; a scratch element using `bg-iris-primary`, `text-iris-body`,
`text-iris-text-muted`, `rounded-iris`, `shadow-iris` and `font-malayalam` produced
computed styles matching spec (background rgb(42,105,181), 17px/27.2px line-height,
colour rgb(92,104,117), 16px radius, matching shadow, "Noto Sans Malayalam" family),
then removed; `document.fonts.check('16px "Noto Sans Malayalam"')` returned true
with `Chat.tsx`'s own `@import` disabled; `/p/arogya-specialty` and the admin
dashboard unchanged by screenshot. A future session must re-derive any of this
rather than rely on it.

Review: the §12.13 report first returned verdict `accept as-is`. Corrected to
`accept with fixes` — 2 of 4 regression screenshots were not captured, and a clean
verdict may not rest on a partial evidence set (§5.10).

Regression check WAIVED by the developer, 2026-08-31 — recorded as a waiver, not a
pass. `/p/iris-hospitals` and `/p/bkm-hospital-payannur` were not screenshotted. No
hospital row in the local database carries either slug, and no component consumes
any `iris-*` token yet, so there is nothing a screenshot could show. Recorded
explicitly so a later task does not assume these routes were checked.

Known and NOT fixed here:
- `text-iris-body-ml` was never exercised. Expected 17px with 32.3px line-height,
  unconfirmed — nothing consumes it yet. First real test is Task 2.
- Trailing whitespace fixed before commit at `frontend/src/index.css:5` — that line
  predates the token diff (it is the blank line after `--font-sans`) and was not
  introduced by this task.
- The Task 1 work lived only in `stash@{0}` from 2026-08-31 17:00:21 +0530 until
  2026-09-01, never committed. Restored with
  `git restore --source='stash@{0}'`; the stash was left intact.

### Catch-up — 2026-09-01

**AGENTS.md governance corrections — CODE COMPLETE, pending commit (branch
`docs/agents-md-corrections`, cut from `origin/main`).**

Six substantive changes to `.agents/AGENTS.md`, made in Claude Chat on 2026-09-01,
resolving three internal contradictions and writing one section that was already
referenced but never existed:

- §6.11 — the CodeRabbit-review paragraph rewritten. Close-out may now fix a
  finding when the fix stays inside the task's `## Files/areas in scope` and fires
  no §10 Opus trigger; every other finding is reported, not actioned. Previously
  read "report it in full without fixing anything," contradicting §12.2 step 7's
  already-permissive text.
- §12.1 — all three summary-table rows rewritten to match what §12.10, §12.15,
  §12.16 and §12.17 actually permit. Two verification rounds caught real
  regressions in this rewrite before commit: the first restored two protections
  dropped from the Claude Code row ("no documentation write before approval," "no
  edit to CURRENT_TASK.md/DECISION.md"); the second fixed a self-contradiction
  where the same row banned force-push outright while §12.10 (untouched) permits
  `--force-with-lease` on Claude Code's own unmerged branch.
- §12.2 step 7 — "It fixes nothing it finds" replaced with the same scoped-fix
  language as §6.11.
- §12.10 — a duplicate, never-committed working-tree bullet (with a
  `protection.Then` paste error) removed. `git log -p` across the file's full
  history confirms the surviving bullet was written once, cleanly, in PR #16 —
  nothing was ever duplicated in any commit.
- §12.16 — new section, written this session. Describes Claude Chat's filesystem
  MCP access (`.agents/` and `docs/` only), including the `D:\npx.cmd` PATH issue
  that caused a same-day outage. Was referenced by §12.17 and §12.18 before it
  existed.
- §12.17 — rewritten. Previously claimed Claude Chat's git write tools were
  disabled in Desktop settings; they were not, confirmed live in this session. Now
  describes the local-only, no-push, no-PR scope of `mcp-server-git`, and which
  tools Claude Chat may use during close-out versus never.
- §12.18 ("One Claude Chat session at a time") — pre-existing, uncommitted content
  from an earlier, separate session. Confirmed via this file's edit history to
  predate any change made here. Left unchanged; included in this commit only
  because it shared the same uncommitted file.

Framing note: §12.16/§12.17 are net-new grants of Claude Chat git/filesystem
capability, not corrections of pre-existing text. Bundled into this commit
alongside genuine contradiction fixes as one file, one topic — matching this
project's established convention for governance-doc commits (Catch-up 2026-08-29).

Process note: this task's own `.agents/CURRENT_TASK.md` change-list was wrong
twice, and both times Order step 2's scope-verification check caught it before
anything was committed — once for a fix that had never actually been missing, once
for the undisclosed §12.18 section. Full detail in this task's `.agents/REPORT.md`
and its two `.agents/DECISION.md` rounds. The check working as designed, not a sign
of trouble.

Known and NOT fixed here:
- `.claude/skills/close-task/SKILL.md` is a tracked repo file (not an external
  Claude Project skill, as this document's Repo Hygiene note previously claimed)
  and still hard-codes "Not fix anything... reporting only" — now superseded by
  the §6.11/§12.2-step-7 text this commit lands. Outside this task's scope. Needs
  its own task.

### Catch-up — 2026-09-02

**Antigravity scoped `command(...)` grant + AGENTS.md §12.10a — DESIGNED AND
EMPIRICALLY VALIDATED, NOT YET INSTALLED (branch `chore/antigravity-command-grant`,
cut from `origin/main` at `3d2d0cf`).**

Reverses the deliberate withholding recorded in Catch-up 2026-08-28. Added AGENTS.md
§12.10a (immediately after §12.10), enumerating exactly what a new `command(...)` grant
in `~/.gemini/antigravity-cli/settings.json` allows, denies, and withholds:

- **Allow (enumerated, no wildcards):** the four `run_*.py` standalone test scripts by
  exact literal relative path; `grep`/`rg`/`ls`/`dir`/`cat`/`type`/`findstr`;
  `git status`/`diff`/`log`/`show`; `npx repomix`.
- **Deny (unconditional):** all deletion (`rm`, `del`, `rmdir`, `Remove-Item`, `ri`,
  `erase`, `rd`); `alembic`; `psql`/`pg_dump`/`pg_restore`; all network tools (`curl`,
  `curl .*`, `curl.exe`, `wget`, `Invoke-WebRequest`, `iwr`); all git-write subcommands
  including `stash`; `sudo`.
- **Not granted:** dev servers (port-kill needs a runtime PID a static permission
  pattern can't scope) and `python -m backend.research.*` (Phase 2 hasn't started).

Design questions resolved empirically, against Antigravity's own documentation and live
dispatches, not assumed:

- **Deny beats allow**, confirmed verbatim from `antigravity.google/docs/permissions`:
  "Conflicting rules are strictly evaluated in priority order: Deny > Ask > Allow."
- **An unmatched command is auto-denied in headless dispatch**, confirmed live:
  dispatching `agy --print "Run the shell command: whoami"` against the real,
  unmodified `settings.json` (zero `command(...)` entries) in the isolated
  `D:\scratch-loop-test` sandbox returned `jetski: no output produced — a tool required
  the "command" permission that headless mode cannot prompt for, so it was
  auto-denied.` Confirms, not merely corroborates, the 2026-08-28 observation that
  Antigravity was blocked, not permitted, on ungranted commands — specific to headless
  dispatch; interactive-mode behavior was not tested.
- **`curl`/`wget` denied outright, not scoped to localhost.** Permission patterns match
  per whitespace-separated token, anchored, as a token-count prefix —
  `command(curl http://localhost.*)` fails to match `curl -s http://localhost:8000`
  because the second token is `-s`, not the URL. Enforcing "localhost only" would mean
  enumerating every flag ordering the model might generate.
- **Deletion denied entirely, not scoped to non-recursive.** On this machine's shell
  (PowerShell), `rm`/`del` are aliases for `Remove-Item`, which takes
  `-Recurse`/`-Force` — flag names no POSIX deny token (`-r`, `-rf`, `-R`) matches.
  There is no pattern that permits a single-file delete without also permitting a
  recursive one.
- **`command(*)` on the ask list is not the answer.** Deny > Ask > Allow means an `Ask`
  entry on `*` would outrank every `Allow` entry, prompting before every enumerated
  script and defeating unattended running entirely.

**A second empirical round (2026-09-02, same day) found and resolved a further gap
before any install.** The developer ran `agy --print "Run: python
backend/run_ml_postprocess_test.py"` from the repo root against the real settings.json
(still just the original two directory-scoped `read_file`/`write_file` entries) and got
`required the "read_file" permission ... auto-denied` — despite
`read_file(D:\Hospital\hospital-ai-platform)` already covering that directory.
Investigated live, with the developer's explicit, narrow, revoked-on-completion
permission to modify the real settings.json for this purpose only (backup at
`settings.json.bak`, restored and verified byte-identical via `cmp` afterward):

- A file read via **absolute path** (either slash direction) succeeded immediately
  against the unmodified directory grant — the pattern and the documented "recursive
  read access to all contained files/folders" claim are both correct.
- The same file via **relative path** failed, and adding a bare relative-form grant
  (`read_file(backend)`) did not fix it.
- Passing **`--add-dir "D:\Hospital\hospital-ai-platform"`** to the `agy` invocation
  fixed it immediately, with zero settings.json changes beyond the original two
  entries. The missing piece was dispatch-time workspace-root registration, not
  settings.json content.
- With `--add-dir` set, the exact, already-drafted `command(python
  backend/run_ml_postprocess_test.py)` string was added and the real script executed
  for real: 26 passed, 0 failed, live output pasted in this task's chat transcript.
  No pattern in the drafted allow/deny lists needed to change.

**Conclusion: every already-drafted `read_file`/`write_file`/`command(...)` pattern is
correct as written. Claude Code's own dispatch of Antigravity must pass `--add-dir
<repo-root>` (or equivalent workspace-root registration) for any of them to resolve a
relative path at all** — recorded in AGENTS.md §12.10a's prose. Without it, every
relative-path grant fails exactly as observed, regardless of how carefully the
permission strings are written.

**Process incident during the investigation, recorded in full per §5.10.** A Bash
heredoc used to write a test settings.json collapsed `\\` to `\` in transit, producing
invalid JSON — caught immediately by the same `python -c "import json..."` validation
habit used throughout this task, before any dispatch was attempted against the
corrupted file. Restored from `settings.json.bak` via `cp` and verified byte-identical
with `cmp` (exit 0) before continuing. All subsequent test files were written with the
Write tool and installed via `cp`, which preserved escaping correctly.

**Found, NOT fixed here: `--dangerously-skip-permissions`.** Antigravity's own CLI
offers this flag, which auto-approves every tool call and bypasses the entire
allow/deny engine designed in §12.10a — discovered incidentally, surfaced in the CLI's
own denial messages during this task's testing (e.g. "Alternatively, re-run with
--dangerously-skip-permissions to auto-approve all tools"). Nothing in `settings.json`
or in §12.10a prevents a future dispatch — a careless invocation, a misconfigured
script, or a compromised session — from passing this flag and voiding every deny rule
at once. Out of scope here: this task concerns `settings.json` content, not how `agy`
is invoked or what wraps it. Needs its own task if a durable defense is wanted (e.g. a
dispatch wrapper that refuses to pass the flag through).

**`~/.gemini/antigravity-cli/settings.json` is NOT currently live with this grant.**
The file on disk remains the original two-entry version (`read_file`/`write_file` on
the repo directory only, zero `command(...)` entries) throughout this task. The design
is proven to work — not installed. Pasting the printed JSON block by hand, validating
it parses as one object, and confirming one real dispatch runs a granted command all
remain the developer's next steps, same approval gate as always (§12.15).

`git diff .agents/AGENTS.md docs/MASTER_PLAN.md` confirmed exactly these two files
changed, nothing else.

Scope: `.agents/AGENTS.md`, `docs/MASTER_PLAN.md`. Related: `.agents/CURRENT_TASK.md`
dated 2026-09-01 (amended 2026-09-02, `§12.10a content` section only).

### Catch-up — 2026-09-01 (second entry)

**Governing-doc corrections — nine lines, docs only.**

A full cross-read of `AGENTS.md`, `docs/STATUS.md` and `docs/MASTER_PLAN.md` found
seven lines that were factually wrong or structurally broken. Two further edits were
added during execution after the failures below. No code, schema, migration or
process change.

`docs/STATUS.md` (four): the Phase 1 `1.3 Sarvam translation upgrade` row and the
Notes "Next up for Phase 1" bullet both still pointed at Task A as upcoming after
PR #19 merged — the same failure pattern PR #18 fixed once before. The header read
"Last updated: 2026-08-22" with eight later entries below it. The Phase 2 heading
cross-referenced MASTER_PLAN.md §4; research is §3.

`.agents/AGENTS.md` (five): §2's Translation bullet still described the Sarvam client
as "not yet built". §2's Database bullet still described the Neon migration as in
progress, though it completed 2026-08-09 and the Render instance was deleted the same
day. §3's `ml_postprocess.py` table row had no path column and no closing pipe.
§12.12 gained a paragraph separating the loop-driver model from §10's review tier.
§12.15 gained `AGENTS.md` on the governing side, closing a gap that let the driver
rewrite the document governing it.

**Two process failures during this task, both recorded because both were expensive.**

First, the loop ran on Haiku, which §12.12 does not permit. It passed the §6.10
branch gate by asserting two commit hashes without pasting the `git log` output
behind them. Both hashes were correct; the evidence was absent, which is a §5.10
breach. Edit 8 exists because of this.

Second, Claude Chat then wrongly accused the agent layer of fabricating one of those
hashes. It tested `git branch --contains <branch-commit>` against `origin/main`,
which can never return `main` under squash merge, and read the empty result as
"unmerged". `docs/STATUS.md` Catch-up 2026-08-29 (second entry) already records this
exact trap for PR #17. The accusation was written into `.agents/DECISION.md` and into
a draft of AGENTS.md §12.12 before being caught and retracted; the §12.12 text as
merged states only what is true.

Known and NOT fixed here: the STATUS.md archive split; the out-of-order Catch-up
entries after the Notes section; the `PR #TBD` in Catch-up 2026-08-27;
MASTER_PLAN.md's overlapping §7/§7a/§7b schedules; and §10's Sonnet list naming
"frontend admin UI", which does not cover patient-facing frontend.

### Catch-up — 2026-09-02 (second entry)

**Unattended halt loop — code complete, tested, registered, and live-verified.**

Added `.agents/hooks/halt_answerer.py`, a Claude Code `Stop` hook that auto-answers
AGENTS.md §12.5 halt conditions 3 and 4 (both fully deterministic, fixed answers
written directly in Python — no model is ever invoked for either, so "no scope
change possible" is true by construction) and condition 6 (a tool-restricted
`claude -p --model sonnet --restricted` dispatch that independently re-runs §12.4's
four-part reversibility test and writes nothing if any part fails). Conditions 1, 2
and 5 always halt for the developer, no exceptions. Never passes
`--dangerously-skip-permissions`; every dispatch passes `--add-dir <repo-root>`;
`ANTHROPIC_API_KEY` presence (never its value) gates every path before any dispatch.
A three-halt cap persists to `.agents/runs/` and resets on a new task; a stale
handoff left over from an already-closed task is now detected and skipped rather
than silently reprocessed. `.agents/hooks/run_halt_answerer_test.py` covers all of
this in 22 synthetic-fixture cases with zero real `claude` calls.

Three AGENTS.md edits, as approved (revised once mid-task at the developer's
correction — condition 4 was originally designed to dispatch a model for no real
reason and was converted to pure Python to match condition 3): §12.10 bans the
bypass flag on any dispatch; §12.10a requires `--add-dir` on every Antigravity
dispatch; §12.15 adds the narrow DECISION.md write exception, now correctly scoped
to conditions 3/4 (deterministic) and 6 (dispatched) after the mid-task correction.

**A four-lens code review caught two Critical bugs before this report, both fixed
and re-tested:** an uncaught crash on non-UTF-8 handoff content, and a stale
leftover handoff from a closed task being silently reprocessable on a fresh task's
first Stop event.

**A separate, more serious design gap was caught by the developer, not the
automated review: the write-restriction mechanism (`--allowedTools
"Write(.agents/DECISION.md)"`) does not actually restrict anything.** Claude Code
only enforces path-scoped permission rules for `Edit`/`Read`, never `Write` — a
`Write(<path>)` rule is silently unconsulted. Two open GitHub issues
(anthropics/claude-code #1188, #67849) describe exactly this failure mode in
headless `-p` mode on Windows. Redesigned to use `Edit(.agents/DECISION.md)`
instead (the hook now pre-creates the file with a placeholder for the answerer to
Edit, since Edit needs existing content), plus `--disallowedTools "Bash PowerShell
WebFetch Write"` as defense in depth.

**Finding 6 is resolved.** Two real adversarial `claude -p` dispatches (isolated temp
directories, the exact shipping command) confirmed the write restriction live, in
both directions: round 1 showed the bare `Write` tool fully blocked; round 2 targeted
`Edit`'s own path-scoping specifically — the model was explicitly instructed to use
Edit against a pre-existing decoy file and was denied, while in the SAME run Edit
succeeded against `.agents/DECISION.md`. Because the same tool both failed against
one path and succeeded against the other in one session, the denial can only be
explained by path-scoping, not a blanket Edit-tool block. This directly answers the
failure mode described in two open GitHub issues (anthropics/claude-code #1188,
#67849 — path-specific `allowedTools` rules silently ignored in headless `-p` mode on
Windows): it did not reproduce here, on Claude Code `2.1.250`, with this exact flag
set. `halt_answerer.py`'s docstring now carries this result instead of a pending-test
note. `.claude/settings.json` registration remains the developer's own action
regardless — nothing here authorizes registering the hook automatically.

### Catch-up — 2026-09-02 (second entry)

**Interactive-mode and review-shape governance docs — COMPLETE.**

Added AGENTS.md §12.19 (interactive vs headless Claude Code is a binary per-task
choice, not a spectrum — interactive is now the default and the halt-answerer from
PR #23 is a fallback for genuinely unattended runs; plus the related finding that
Claude Code only enforces path-scoped permissions via `Edit(<path>)`, never
`Write(<path>)`) and §12.20 (the two-prompt review shape — one paste to start a task,
one for a consolidated fix round, `.agents/REPORT.md` as the new standing
end-of-task write — with the explicit caveat that this targets relay friction, not
review depth). Docs only, no code touched. `git diff .agents/AGENTS.md` confirmed
only these two subsections were added, nothing else changed. MASTER_PLAN.md §9
appended.

### Catch-up — 2026-09-03

**AGENTS.md §6.12 — squash-merge verification rule added — COMPLETE (branch
`docs/squash-merge-verification-rule`, cut from `origin/main`).**

PR: #26
Commits: 5aafc14

Added AGENTS.md §6.12, a new subsection immediately after §6.11: verifying whether
work is merged into `main` must check file content at a revision
(`git show origin/main:<path> | grep "<string>"`), never the commit graph
(`git branch --contains`, `git merge-base --is-ancestor`) — this repo squash-merges,
so a squash-merged commit is never an ancestor of `main` even after a clean merge,
and both graph-based checks return a confident, wrong "not merged" as a result.
This trap has now caused three separate incidents: two already recorded in this
file (Catch-up 2026-08-29 second entry; Catch-up 2026-09-01 second entry, the false
fabrication accusation on PR #17), and a third on 2026-09-02 where Claude Code
reached the correct halt decision on a merge-status question but supported it with
two invalid checks of this kind alongside the one valid one.

Docs-only change. No commands were run beyond git, since there is no code to test.
`git diff .agents/AGENTS.md` confirmed only the one new subsection was added and
nothing else changed.

Deferred: none — a single, self-contained rule addition.

### Catch-up — 2026-09-03 (second entry)

**Task 2 — chat-stream [TRANSLATION_UNAVAILABLE] sentinel — CODE COMPLETE
(branch `feat/chat-stream-translation-sentinel`, cut from `origin/main`).**

PR: #27
Commits: 27ee8cd

Emits a bare, non-JSON SSE sentinel frame, `data: [TRANSLATION_UNAVAILABLE]\n\n`,
from the two English-to-Malayalam `TranslationUnavailableError` branches that
live lexically inside the `/chat-stream` endpoint's `event_generator` in
`backend/app/api/v1/endpoints/ai.py`: the STATUS-reply site (line 532) and the
booking-validation-error site (line 940). Deliberately a raw literal string,
not `json.dumps(...)` like every other frame in this file — `json.dumps(...)`
would wrap it in quotes and make it valid JSON, defeating the point, since
`useHospitalChat.tsx` silently skips any frame that fails `JSON.parse()`.

Order step 2's own gate caught a real discrepancy before any edit: the raw
`grep -n "TranslationUnavailableError"` count inside `chat_stream` is 3, not
the 2 the task file expected — a third match at line 425 is the
Malayalam-to-English site (translating the patient's incoming question),
already named out of scope elsewhere in the same task file. Confirmed with
the developer via `AskUserQuestion` before proceeding on the two
English-to-Malayalam sites only (STATUS reply, booking-validation error).

Out of scope, explicitly: the welcome-greeting `TranslationUnavailableError`
branch (served by `GET /welcome/{hospital_id}`, a different endpoint with no
SSE stream), and both Malayalam-to-English call sites in `/chat-stream`
(including line 425's ml→en site found during the step-2 check).

`backend/run_chat_stream_sentinel_test.py` — new, standalone, no pytest.
Drives the real `chat_stream()` function end-to-end for both sites (not an
isolated snippet test), with `_translate_async`, `classify_user_intent`,
`_update_patient_ctx`, `build_context`, the OpenAI streaming client, and
`validate_booking` all monkeypatched — no real network, no real DB, no real
LLM call. Asserts: the exact frame `data: [TRANSLATION_UNAVAILABLE]\n\n`
appears in the yielded output at each site; `json.loads()` on its payload
raises `json.JSONDecodeError`, proving it is genuinely invalid JSON and not
just visually different; an ordinary `json.dumps(...)`-wrapped frame later in
the same run still parses as valid JSON, unaffected.

```text
[Translation] en->ml failed at STATUS reply: TranslationUnavailableError
[Translation] en->ml failed at booking-validation error: TranslationUnavailableError
PASS status_site_sentinel_frame_present
PASS status_site_has_a_normal_frame_too
PASS status_site_normal_frame_is_valid_json
PASS status_site_sentinel_payload_is_invalid_json
PASS booking_site_sentinel_frame_present
PASS booking_site_has_a_normal_frame_too
PASS booking_site_normal_frame_is_valid_json
PASS booking_site_sentinel_payload_is_invalid_json

8 passed, 0 failed
EXIT CODE: 0
```

`app/api/v1/endpoints/__init__.py` does `from .ai import router as ai`, which
overwrites the package's own `ai` attribute with the router object — a plain
`import app.api.v1.endpoints.ai as ai` resolves via attribute access and
would silently bind the router, not the module. The test script imports via
`importlib.import_module("app.api.v1.endpoints.ai")` instead, which reads
`sys.modules` directly and is unaffected by the shadowing.

`git diff backend/app/api/v1/endpoints/ai.py` confirmed exactly two lines
added, nothing else touched. No Alembic command run, no migration file
created. No frontend file touched — this task has no consumer for the
sentinel; that is design frame 07, deferred until a frontend task picks it up.

Deferred: none — a single, self-contained backend signal addition.

### Catch-up — 2026-09-03 (third entry)

**Task 1b — IRIS design token addendum — CODE COMPLETE
(branch `feat/iris-token-addendum`, cut from `origin/main`).**

PR: #28
Commits: a972eda

Added three tokens to the `@theme` block in `frontend/src/index.css`, closing
three of the five gaps found by Task 3's Order step 6 token map — Task 3
remains halted, waiting on these, and resumes once this merges:

- `--color-iris-accent-surface: #EAF2F2` — a pale tint of `--color-iris-accent`
  (#0E7C86), used as the background of the language-switch notice in design
  frame 06.
- `--text-iris-ui-ml: 15px` / `--text-iris-ui-ml--line-height: 1.9` — the
  Malayalam counterpart to `--text-iris-ui` (15px/1.6). Task 1 defined only
  one Malayalam size (`--text-iris-body-ml`, 17px); Malayalam needs the taller
  line-height at every size, not just body.
- `--radius-iris-sm: 12px` — the nested radius for the language-toggle pill's
  inner rounded rectangle (sits inside the 16px `--radius-iris` container).
  Deliberate naming asymmetry with `--radius-iris` (no `-md` suffix) — not
  "fixed" here, since renaming a merged Task 1 token is out of scope.

Two further mismatches from Task 3's report were triaged as design-side, not
token gaps, and deliberately get no token: 13px/line-height-1 on the
language-toggle pill labels (an export artifact — `--text-iris-label`'s
13px/1.5 centres identically in a flex-centred pill), and 15px at two
different line-heights (1.9 in most places, 1.4 on the stop-button labels) —
an inconsistency in the design file itself, which the developer is
correcting to 1.9 everywhere so `--text-iris-ui-ml` covers every site.

All 22 of Task 1's existing properties are unchanged — confirmed by reading
the `@theme` block off disk before editing and by `git diff` after.

**Verification.** `npm run build` exits 0 — noted explicitly that this proves
only that the file compiles, not that the tokens work; Tailwind v4 generates
no output at all for a class referencing a missing token, silently. The real
check: a scratch element was added to a real source file
(`frontend/src/main.tsx`, temporarily, then fully reverted — confirmed absent
from the final `git diff`) using all three new utility classes, since
Tailwind's JIT only generates CSS for classes it finds in scanned source
files — an earlier attempt to inject the classes via a live browser-console
script produced a false negative (zero effect) on even Task 1's own already-merged
tokens (`text-iris-body-ml`, `rounded-iris`, `bg-iris-primary` all read as
unstyled too), which is what surfaced this methodology issue rather than an
actual regression. Computed styles read via the real dev server:

```text
{"fontSize":"15px","lineHeight":"28.5px","borderRadius":"12px","backgroundColor":"rgb(234, 242, 242)"}
```

All three match expected exactly: `text-iris-ui-ml` → 15px / 28.5px (15×1.9);
`rounded-iris-sm` → 12px; `bg-iris-accent-surface` → rgb(234, 242, 242) (#EAF2F2).

Nothing consumes any of the 25 `iris-*` properties yet — Task 3 remains the
first consumer, once it resumes.

Deferred: none — three tokens added, two explicitly declined as design-side.

### Catch-up — 2026-09-03 (fourth entry)

**Task 3 — IRIS patient chat widget rebuild — CODE COMPLETE
(branch `feat/iris-widget-rebuild`, rebased onto `origin/main`).**

PR: #29
Commits: 529fc5c

Rebuilt `Chat.tsx` and `ChatMessage.tsx` in the `iris-hospitals` theme against
the approved Claude Design LIGHT design (frames 01/02/03/04/05/06/08), the
first consumer of any of the 25 `iris-*` tokens from PR #25 and PR #28.
Presentation only — `useChatCore`'s interface is unchanged, no hook, no
data-flow, no backend change. `index.tsx` (the DARK page shell) and
`AnimatedIntro.tsx` are untouched; `index.tsx` already imports `Chat` by
relative path, so the light rebuild takes effect without editing it.

**Halted twice before this run, both real gates:**
- Order step 2's own count check (grep for `"iris-"`) would have shown 19
  matches against an expected 22 (Task 1b's addendum made it 25/19) — the
  gate deliberately reads the whole `@theme` block instead, since
  `--font-malayalam`, `--radius-iris`, `--radius-iris-sm` and `--shadow-iris`
  don't contain the substring `"iris-"`.
- Order step 5's token map found two 15px Malayalam sites (frame 03's
  "നിർത്തുക", frame 05's "നിർത്തൂ") at an inconsistent `1.4` line-height
  against `1.9` everywhere else. The design's own UI could not edit
  `line-height` inside a `font:` shorthand, so this needed a hand-edit to the
  exported `.dc.html` directly — confirmed landed only after the file was
  re-read fresh from disk a third time and grepped for zero remaining
  `15px/1.4` matches.

**Design source moved mid-task.** The `claude-design` MCP server was serving
a stale cached copy — its `IRIS Chat Widget.dc.html` etag never changed
across a confirmed edit. The design is now a local export at
`.design/IRIS Chat Widget.dc.html` (untracked, never staged), diverging from
the Claude Design project by the four corrected line-height values.

**Two genuine token gaps found in frame 05 (voice input), resolved without
touching `index.css`:** `#E4C5BA` (recording-state card border) and
`#E7EDF4` (transcribing progress-track background) have no matching
`iris-*` token. Per the token rule (no new token, no raw inline value, no
nearest-token substitution), both are rendered via CSS `color-mix()` derived
from `--color-iris-danger` (33%) and `--color-iris-border` (53%)
respectively — computed values verified at `rgb(229,195,186)` and
`rgb(233,238,243)`, within 2/255 per channel of the design's exact hex.

**Frame 07 (translation-unavailable) deliberately not built.** Confirmed
unreachable from `Chat.tsx` alone: it delegates to `useChatCore` →
`useHospitalChat`, and `useHospitalChat.tsx:137`'s `catch { /* skip */ }` is
exactly where the `[TRANSLATION_UNAVAILABLE]` sentinel (Task 2, PR #27) is
silently dropped. Detecting it needs a change to that shared hook, used by
all three themes — out of scope here, deferred to its own task with
developer sign-off.

**Other disclosed implementation decisions, none touching the shared hook or
`index.css`:**
- The design's "stop generation" chip (frames 03/05) is not rendered —
  `useChatCore` exposes no `stopGeneration()` capability, and this is not a
  regression: the dark theme never had one either. Rendering it would mean
  either a non-functional button or a hook change.
- Frame 05's transcribing state omits the dashed live-partial-transcript box
  — the hook exposes no partial-transcript field, only the final `inputText`
  once transcription completes. Not fabricated.
- Frame 05's recording-state elapsed timer and frame 06's "switched
  language" notice are implemented as local, ephemeral component state in
  `Chat.tsx` (a `setInterval` counter; a `setTimeout`-dismissed toast) — not
  sourced from the hook, not persisted, not a data-flow change.
- `Chat.tsx`'s own redundant Malayalam font `@import` was removed, per the
  task file — `index.html` (PR #25) already loads Noto Sans Malayalam
  globally and the `font-malayalam` token-derived utility already exists.
  Verified no rendering change: the scratch-element check below resolved
  `font-family: "Noto Sans Malayalam", Manjari, sans-serif` correctly.
- The 13px/line-height-1 language-toggle pill labels use `--text-iris-label`
  (13px/1.5), per the design-side triage already recorded in Catch-up
  2026-09-03 (third entry) — confirmed still present in the re-read design,
  unchanged, as expected (an export artifact, not something meant to be
  fixed).
- Desktop vs mobile sizing (panel width, padding, bubble max-width) is
  implemented as a live Tailwind responsive breakpoint (`md:`), not two
  fixed exports, matching how the existing dark theme already sizes itself
  independent of the browser viewport — this task's own read is that the
  design's "what changes at desktop" panel describes responsive behaviour.
- Logo asset placed at `frontend/src/themes/iris-hospitals/iris-logo.png`,
  imported as a bundler module in `Chat.tsx`. No genuine existing convention
  for theme logo assets was found under `frontend/src/themes/` (the one
  file there, `iris-hospitals/logonewiris.png`, is a dead, unused duplicate
  — the theme's real, live logo is served from `frontend/public/` and
  referenced by absolute URL in `AnimatedIntro.tsx`). Flagged to the
  developer, who chose to place the new logo under the theme directory as
  the task file originally specified, establishing that pattern going
  forward rather than following the pre-existing `public/` convention.
- Small decorative radii (1–8px on icon bars, dots, waveform strokes) use
  Tailwind's structural utilities, not `iris-*` tokens — not design-system
  scale values, per the standing reasoning carried from the token-map step.

**Verification.** `npm run build` exits 0 — stated plainly that this proves
compilation only, not that any token works. Real verification: a scratch
harness (`ChatMessage` and `Chat` rendered directly, no backend needed since
all four target checks are either static text or local component state) was
added to `frontend/src/main.tsx`, then fully reverted — confirmed absent
from the final `git diff`. Computed styles read from the live dev server:

```text
text-iris-body-ml  → font-size 17px, line-height 32.3px (17×1.9)
text-iris-ui-ml    → font-size 15px, line-height 28.5px (15×1.9)
radius-iris-sm     → border-radius 12px
color-iris-accent-surface → background-color rgb(234, 242, 242)
```

All four match expected exactly. Screenshots captured of the rendered widget
(header, language toggle, greeting bubble, suggestion chips, composer) after
an initial Browser-pane rendering glitch (solid black frame despite
correct, independently-verified DOM/computed-style content) was resolved by
a fresh navigation. The recording and transcribing mic states were not
visually screenshotted — `micState` transitions depend on real voice
activity detection, which fails to initialize in this environment (VAD
model file load error, unrelated to this task's code) — waived with reason,
not claimed as passed; the `color-mix()` values driving those two states
were verified numerically instead (above).

Deferred: frame 07 (own task, needs shared-hook change); the four disclosed
implementation decisions above, all reported rather than hidden.

### Catch-up — 2026-09-03 (fifth entry)

**PR #29 follow-up — fixed duplicate "IRIS സഹായി" render during streaming.**

While the developer was testing PR #29's rebuilt widget live, a real UI bug
surfaced: the moment a new assistant reply starts streaming, two "IRIS
സഹായി" blocks appeared simultaneously — an empty `ChatMessage` bubble (the
just-appended placeholder message, `content: ''`) rendered by the
`messages.map()` loop, and the separate "thinking" indicator block, since
both check the same condition (`isStreaming && last message content === ''`).
The dark theme has this identical structural pattern and is presumed to have
had the same defect, just visually unnoticeable against a dark background;
the light theme's visible white bubble/shadow made it obvious.

Fix: skip rendering the real `ChatMessage` bubble specifically for the last
message while it is still the empty streaming placeholder — the thinking
indicator covers that exact state, and the real bubble takes over normally
once content starts arriving.

Verified live: sent a real message against the local backend; confirmed only
one "IRIS സഹായി" label renders before/during the reply. (The reply itself
failed with `openai.RateLimitError: insufficient_quota` — the local OpenAI
key has no credits remaining — unrelated to this fix.)

PR: #29
Commits: fdf60dd

### Catch-up — 2026-09-03 (sixth entry)

**IRIS page shell — light theme + faster intro + dev-tooling overlay fix —
CODE COMPLETE (branch `feat/iris-intro-lighter-and-faster`, cut from
`origin/main`).**

PR: #30
Commits: 8a31a6e

Developer-directed, iterative visual work discovered live while testing PR
#29's rebuilt widget in a browser — outside that PR's scope (`index.tsx` and
`AnimatedIntro.tsx` were explicitly untouched by Task 3), kept as separate,
unrelated-feature work per §5.8.

- `frontend/src/themes/iris-hospitals/index.tsx` — the persistent page shell
  around the chat widget (header, hero copy, background) is now a light
  theme, reusing the same `iris-*` tokens the widget itself uses
  (`bg-iris-surface`, `bg-iris-surface-raised`, `text-iris-text-primary`,
  `text-iris-text-muted`, `text-iris-primary`, `bg-iris-accent-surface`/
  `text-iris-accent`) rather than inventing new ad hoc colours. Previously a
  dark navy/indigo gradient with white/light-indigo text.
- `frontend/src/themes/iris-hospitals/AnimatedIntro.tsx` — the entry
  animation (logo → tagline → demo conversation → CTA → transition) is
  compressed from ~12.6s to ~7s total. Every internal timeout scaled
  proportionally (verified by hand to land within a few ms of 7000ms), so
  the same sequence of beats still plays, just faster. Its own background
  gradient (blue, distinct from the page shell's) was left unchanged — only
  the page shell's persistent background was reported as "purple."
- `frontend/vite.config.js` — new file (none existed before). Sets
  `server.hmr.overlay: false` only. Discovered while testing the above:
  Vite's dev-only fullscreen HMR error overlay was blocking the page,
  triggered by a pre-existing, unrelated issue (the `@ricky0123/vad-web`
  voice-detection library's WASM asset path being flagged by Vite's
  module-import checker, even though the asset loads fine via a plain URL
  string at runtime). This suppresses the on-page popup only — the
  underlying warning still prints to the browser console, and the actual
  voice-detection initialization issue is untouched (would need a change to
  the shared `useHospitalChat.tsx` hook, out of scope here).

No `iris-*` design tokens were added, edited or removed — `index.css`
untouched. No hook, data-flow or backend change.

Deferred: none.

### Catch-up — 2026-09-15

**Chat-stream welcome-message translation fix, both call sites — CODE
COMPLETE (branch `fix/chat-stream-welcome-translation`, cut from
`origin/main` at `168392f`, PR #35).**

PR: #36
Commits: 58cdcf5

Fixes the bug recorded as suspected/unconfirmed in the Notes/Open Questions
entry above (found 2026-08-29). `chat_stream`'s new-session greeting block
yielded `hospital.welcome_message` raw into the SSE stream with no
translation call, regardless of `request.language` — a Malayalam session
(`language="ml"`) with an English-authored `welcome_message` would see the
greeting in English. Fixed by capturing the greeting into a local variable,
translating it via the same `normalise_malayalam(await _translate_async(...))`
pattern already used by `GET /welcome/{hospital_id}`, and yielding the
(possibly translated) local variable instead of the raw ORM field. On
translation failure, falls back to the untranslated text rather than killing
the stream; failures log only `type(e).__name__`, never greeting text.

**Scope widened mid-task, developer-directed:** before-evidence proved a
Malayalam-authored `welcome_message` is a real, buildable case, and both this
new call site and the existing `get_welcome()` pattern it copies assumed the
source text is always English. Fixing only the new site would have shipped a
fresh bug (garbling Malayalam-authored greetings) while leaving the identical
latent assumption in `get_welcome()` untouched. Added a new pure predicate,
`contains_malayalam(text: str) -> bool` (`backend/app/services/ml_postprocess.py`),
and gated the en→ml translation call at both sites on it: already-Malayalam
text skips translation and passes through as-is.

Verification: before/after raw SSE evidence pasted in full in
`.agents/runs/before-evidence-chat-stream-welcome.md` and
`after-evidence-chat-stream-welcome.md`, covering all four combinations
(English/Malayalam-authored `welcome_message` × `language="en"`/`"ml"`).
`contains_malayalam` unit-tested directly (pure English/pure
Malayalam/mixed/empty), re-run fresh during review with identical output.
Four independent read-only review lenses (scope, rules, evidence, blast
radius) confirmed the diff touches only the three scoped files, no `## Do NOT
touch` item was touched, and both functions' output shapes are unchanged on
every code path.

**Review tier escalated during first-pass review: Opus 5, high effort**, not
the Sonnet 5/medium originally scoped — the diff adds two new
`logger.warning(...)` calls in a previously unlogged branch, which
independently fires `AGENTS.md` §10's "touches logging" trigger regardless of
the (confirmed clean) log content. Full report: `.agents/REPORT.md`.

Deferred: no general source-language detection — `contains_malayalam` only
distinguishes English from Malayalam. A `welcome_message` authored in a third
language would still be fed into the en→ml translator unchanged.
