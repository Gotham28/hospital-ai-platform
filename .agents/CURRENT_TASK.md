# Current Task

## Feature
Fix the chat-stream new-session greeting so it goes through the same
translation and normalisation treatment that `GET /welcome/{hospital_id}`
already applies to `hospital.welcome_message`. Today the greeting block inside
`chat_stream`'s `event_generator` (guarded by
`_turn_ctx.get("_is_new_session")`) yields `hospital.welcome_message` directly
into the SSE stream with no translation call at all, regardless of
`request.language`. When a hospital has a Malayalam-serving session
(`language="ml"`) and an English `welcome_message` configured, the greeting
would arrive untranslated.

This bug has never been observed live — `docs/STATUS.md` records it as
suspected/unconfirmed, because no hospital in the local dev DB currently has
`welcome_message` set. Confirmed via read-only SQL against the local DB
(`SELECT id, name, welcome_message FROM hospital`) — all rows show `NULL`.

## Plan reference
Not in `docs/MASTER_PLAN.md`. Targeted bug fix, scoped directly in chat by the
developer. Not part of MASTER_PLAN.md §1.3a (Sarvam translation upgrade tasks
A/B/C) — this is a call-site gap in existing translation wiring, not new
translation-provider work.

Branch: `fix/chat-stream-welcome-translation`, cut from `origin/main`
(`168392f`, PR #35) by Claude Code per AGENTS.md §6.10.

## Investigation findings (read-only, already done)

- **Buggy block** — `backend/app/api/v1/endpoints/ai.py`, inside `chat_stream`
  (`POST /chat-stream`), inside the nested `event_generator`, currently at
  lines 453-456 (STATUS.md's cited 442-445 has drifted since PRs #31/#32 added
  `safe_event_stream`):
  ```python
  if _turn_ctx.get("_is_new_session"):
      hospital_for_welcome = db.query(Hospital).filter(Hospital.id == request.hospital_id).first()
      if hospital_for_welcome and hospital_for_welcome.welcome_message:
          yield f"data: {json.dumps(hospital_for_welcome.welcome_message)}\n\n"
  ```
  The query already filters by `request.hospital_id` (tenant-safe). No
  translation call of any kind is made before the `yield`.

- **Correct existing pattern** — `GET /welcome/{hospital_id}` (`get_welcome`),
  currently at lines 224-238 (STATUS.md's cited line 228 has drifted the same
  way):
  ```python
  if hospital.welcome_message and hospital.welcome_message.strip():
      base_en_greeting = hospital.welcome_message.strip()
      try:
          base_ml_greeting = normalise_malayalam(await _translate_async(base_en_greeting, source="en", target="ml"))
      except TranslationUnavailableError as e:
          logger.warning("[Translation] en->ml failed at welcome greeting: %s", type(e).__name__)
          base_ml_greeting = f"{base_en_greeting}"
      except Exception as e:
          logger.warning("[Translation] en->ml unexpected failure at welcome greeting: %s", type(e).__name__)
          base_ml_greeting = f"{base_en_greeting}"
  else:
      ...
  ```
  On any translation failure it falls back to the untranslated English text
  and logs a type-only warning (no greeting text logged) — matches §5.6.

- `is_malayalam = request.language == "ml"` is already computed earlier in
  `chat_stream` (before `event_generator` is defined) and is already read as a
  closure variable inside `event_generator` elsewhere in the same function
  (e.g. the CANCEL branch). No new variable is needed to gate the fix.

- `_translate_async`, `TranslationUnavailableError`, and `normalise_malayalam`
  are already imported at the top of `ai.py` (lines 24-25). No new imports
  needed.

- A third pattern also exists in the same file, inside the STATUS-check branch
  of the same `event_generator` (~line 527-535): on
  `TranslationUnavailableError` it yields an extra
  `data: [TRANSLATION_UNAVAILABLE]\n\n` sentinel event before still sending the
  untranslated reply. This task does NOT use that pattern — the developer's
  instruction is to match `GET /welcome/{hospital_id}` specifically, which has
  no sentinel event. Do not invent a hybrid of the two.

## Files/areas in scope
- `backend/app/api/v1/endpoints/ai.py` — two blocks:
  - The greeting block inside `chat_stream`'s `event_generator` (lines
    453-456 pre-edit, now 456-467). Changed to:
    1. Capture `hospital_for_welcome.welcome_message` into a local variable.
    2. If `is_malayalam` AND the text does not already contain Malayalam
       (`contains_malayalam` guard), translate via
       `normalise_malayalam(await _translate_async(…, source="en", target="ml"))`
       in a try/except with two except clauses
       (`TranslationUnavailableError`, then `Exception`), each logging a
       type-only warning (`type(e).__name__` only — never the greeting text,
       per §5.6). On failure, leave the local variable at its original
       (untranslated) value — do not raise, do not kill the stream.
    3. Yield the (possibly translated) local variable, not the raw ORM field.
    4. Do not add a `[TRANSLATION_UNAVAILABLE]` sentinel event.
    5. Do not change the existing `if hospital_for_welcome and
       hospital_for_welcome.welcome_message:` truthiness guard.
  - The `GET /welcome/{hospital_id}` (`get_welcome`) translation call (lines
    226-235 pre-edit, now 226-238). Wrapped the existing en→ml translation in
    a `contains_malayalam` guard: if the source text already contains
    Malayalam, skip translation and use the text as-is for `base_ml_greeting`.
    Try/except shape, fallback values, and return unchanged.
- `backend/app/services/ml_postprocess.py` — one new pure function
  `contains_malayalam(text: str) -> bool` and its backing constant
  `_MALAYALAM_RANGE`. No existing function changed.
- `.agents/CURRENT_TASK.md` — this file.

## Scope widened — 2026-09-11, developer-directed

Original scope: the chat-stream new-session greeting block only, copying
GET /welcome/{hospital_id}'s pattern verbatim without editing it.

Widened to cover both call sites after before-evidence (Run C, in
.agents/runs/before-evidence-chat-stream-welcome.md) confirmed that the
pattern being copied carries an inherited defect: both sites assume
source="en" unconditionally. Post-fix, a Malayalam-authored welcome_message
would be fed into an en->ml translation call and likely garbled. Today it
passes through clean, so shipping the narrow fix alone would REPLACE a
working behaviour with a broken one at the new site, while leaving the same
latent defect untouched at the old one.

Fixing one site and not the other would leave two copies of one bug in two
different states. Both are therefore in scope for this task.

Added to scope:
- backend/app/api/v1/endpoints/ai.py — GET /welcome/{hospital_id}
  (get_welcome), previously "do not touch, pattern only"
- backend/app/services/ml_postprocess.py — one new pure predicate function

Not in scope, still: the non-streaming POST /chat welcome handling, any
Redis/cache work, any frontend file, any translation.py change.

## Do NOT touch
- `backend/app/services/translation.py` — no change needed there for this fix.
- Any Redis code — the translation cache is a separate, unstarted task
  (MASTER_PLAN.md §1.3a Task C).
- The non-streaming `POST /chat` endpoint's own welcome-message handling
  (~lines 395-398), which prepends `hospital.welcome_message` to `answer`
  rather than streaming it — different call site, not part of this bug report,
  not touched.
- ~~The `GET /welcome/{hospital_id}` handler itself — originally read as a
  pattern to copy, never edited.~~ **Moved into scope** per the widening
  block above: the `contains_malayalam` guard was added to its existing
  translation call to prevent garbling already-Malayalam text.
- Any file under `frontend/`.
- `docs/STATUS.md` — append-only log, written at close-out with developer
  approval, not part of this task's file scope.
- The untracked clutter already present in `git status` (`.design/`, `assets/`,
  `uploads/`, `.agents/REPORT.md`, `.claude/launch.json`, `.thumbnail`,
  `backend/mock_test.py`, `backend/test_welcome.py`, `cleanup.md`,
  `deck-stage.js`, `docs/SECURITY_FIXES.md`, `scratch_token_volume.py`,
  `support.js`, `test_httpx_leak.py`, `test_relevance.py`, `test_req.py`).
- No Alembic migration — there is no schema change in this task.

## Execution route
- B — Claude Code drives Antigravity for the mechanical `ai.py` edit, then
  reviews.
- **Narrowing, developer-directed:** neither Claude Code (per the active
  `antigravity-guard.ps1` hook, which blocks all `Edit`/`Write`/`Bash` writes
  outside `.agents/`, `docs/`, `HANDOFF.md`) nor Antigravity (per AGENTS.md
  §12.10a — dev servers are "NOT GRANTED", and its only permitted Python
  invocations are four unrelated enumerated test scripts) can execute the live
  reproduction (before the fix) or live re-verification (after the fix)
  against a running dev server and local DB. Those two steps are `## Manual
  (developer does)` items below, not agent-executed, for this task only.
- Close-out: manual. Commit, push and PR are `close-task`, developer-driven,
  per AGENTS.md §6.11. The developer stopped this task explicitly at "code
  complete + evidence pasted" — no commit, push, PR, or STATUS.md write from
  the agent layer for this task.

## Manual (developer does)
- [ ] **Before the fix** — set a Malayalam-triggering (i.e. any non-empty)
      `welcome_message` on a local test hospital (e.g. hospital id 4, "Test
      Hospital X", which currently has `welcome_message = NULL`), start a new
      session against `POST /chat-stream` with `language="ml"`, and paste the
      raw SSE response showing the greeting arriving untranslated. If it
      arrives translated already, STOP and report that the bug does not
      exist — do not let the fix proceed.
- [ ] **After the fix** — re-run the identical `language="ml"` request and
      paste the raw response showing the greeting now in Malayalam. Then
      re-run with `language="en"` and paste that too, showing English is
      unaffected.
- [ ] Approve this task file.
- [ ] Review Antigravity's returned diff / `HANDOFF.md` (Claude Code performs
      the mechanical §12.13 first-pass review; the developer makes the final
      call per `review-skill`).

## Agent (does on its own, once scope is confirmed)
- [ ] Dispatch Antigravity to make the three edits described under
      `## Files/areas in scope`: the `chat_stream` greeting block and the
      `get_welcome` `contains_malayalam` guard, both in `ai.py`, plus the new
      `contains_malayalam` function in `ml_postprocess.py`.
- [ ] Read Antigravity's raw output; confirm the diff touches only the named
      lines inside `chat_stream`'s `event_generator`, the named lines inside
      `get_welcome`'s translation call, and the new function in
      `ml_postprocess.py` — nothing else.
- [ ] Run `git diff -- backend/app/api/v1/endpoints/ai.py` and paste it in
      full.
- [ ] Confirm the `hospital_id` filter on the query the fix touches is
      unchanged (§5.1) and that no `if hospital_id == X` branching was
      introduced (§5.2).
- [ ] Produce the §12.13 seven-section first-pass review report.
- [ ] State the §10 suggested review model line.

## Order
1. Dispatch Antigravity with the exact before/after code for all three edits
   (below): the `chat_stream` greeting block, the `get_welcome`
   `contains_malayalam` guard, and the new `contains_malayalam` function in
   `ml_postprocess.py`.
2. Read Antigravity's raw output and diff.
3. Report the diff to the developer for the "after the fix" manual
   verification step above.
4. Produce the first-pass review report.
5. Stop. No commit, push, PR, or STATUS.md write — the developer said close-out
   is manual and theirs for this task.

## Verification required before this is considered done
- [ ] Raw SSE response from `POST /chat-stream`, `language="ml"`, new session,
      test hospital with `welcome_message` set — BEFORE the fix — showing the
      greeting untranslated.
- [ ] `git diff` — full raw output, showing exactly three files changed:
      `backend/app/api/v1/endpoints/ai.py` (two hunks: `get_welcome` guard +
      `chat_stream` translation, plus the import line for
      `contains_malayalam`, all inside this one file),
      `backend/app/services/ml_postprocess.py` (new function), and
      `.agents/CURRENT_TASK.md`.
- [ ] Raw SSE response from the same request — AFTER the fix — showing the
      greeting translated to Malayalam.
- [ ] Raw SSE response from the same request with `language="en"` — AFTER the
      fix — showing English unaffected.
- [ ] Confirm only the expected hunks in `ai.py` changed (`git diff --stat`).

## Flags (AGENTS.md rule triggers)
- §5.1 tenant isolation — the fix touches a query already filtered by
  `request.hospital_id`; the filter itself is not changed, only what happens
  to the field after it is fetched. No cross-tenant read is introduced.
- §5.2 — no `if hospital_id == X` branching anywhere in the fix. The
  translate-if-`is_malayalam` gate is generic per-request-language behavior,
  not per-hospital.
- §5.5 — no disclaimer, legal, or medical wording is authored. If
  `welcome_message` is empty, the block still doesn't fire (unchanged guard).
- §5.6 — the fix's warning logs carry only `type(e).__name__`, never greeting
  text or any patient/user text.
- §5.8 — one feature: the chat-stream greeting translation gap. No unrelated
  cleanup bundled in.
- §5.10 — every claim in this task's evidence must carry pasted raw command
  output, not a description of output.
- §10 Opus triggers — none of the enumerated Opus triggers fire: no new or
  modified query against `Doctor`/`KnowledgeBase`/`Appointment`/`LabTest`, no
  `hospital_id` filter added/removed/edited, no migration, no logging of raw
  patient text, no touch to `services/security.py` or
  `_INJECTION_PATTERNS`, no function signature change, no disclaimer/legal
  wording, no `backend/research/` boundary crossing, no auth/session-token/
  Redis-key change, no `DATABASE_URL`/connection-config change. The new
  `contains_malayalam` function in `ml_postprocess.py` widens that module's
  public surface but does not trigger any §10 Opus item — it is a pure
  addition of a new function, not a signature change or cross-module move.

## Suggested review tier (set at scoping time)
- Sonnet 5, medium effort. No §10 Opus trigger fires (see Flags above); this
  is an ordinary bug fix reusing an already-established translation call
  pattern in the same file.

## Suggested Antigravity model
- Fastest/cheapest available in the selector. The before/after code for all
  three edits, across both files, is fully specified in this file — no
  judgement left for Antigravity to exercise.
