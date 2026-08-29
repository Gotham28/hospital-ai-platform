# Current Task

## Feature
Wire the existing `normalise_malayalam()` normaliser into the three English-to-Malayalam
`_translate_async()` call sites in `ai.py`, so translated Malayalam output is normalised
before it reaches a patient.

## Plan reference
MASTER_PLAN.md §1.3a — Sarvam upgrade execution sequence, Task B (Malayalam
post-processing, "applied to translated output"). This is the second half of Task B;
the module itself landed as Task B1 (PR #11, commit `837001b`).
STATUS.md state at time of scoping: §1.3 marked 🟡 In progress — normaliser module built
but not wired; Task A blocked on the Sarvam API key. B1b is named as next up.

## MASTER_PLAN.md update
- [ ] None — task matches §1.3a Task B above. No §9 append.

## Files/areas in scope
- `backend/app/api/v1/endpoints/ai.py` — add an import of `normalise_malayalam` from
  `app.services.ml_postprocess`, and apply it to the returned string at the three
  English-to-Malayalam `_translate_async()` call sites only.

## Explicitly out of scope
- Formal-pronoun rewriting (അവൻ → അദ്ദേഹം) — split out at B1 scoping time; needs a
  context-conditional rule, not a flat (pattern, replacement) rule.
- Any new or changed rule inside `ml_postprocess.py` — the module is final for this task.
- Per-hospital configurability of normalisation — dropped 2026-08-22; would need a
  Hospital column and an Alembic migration.
- The `_translate_async()` "returns untranslated English on upstream failure" bug —
  MASTER_PLAN.md §1.3a Task A owns it, via the circuit breaker.
- Any Sarvam client work — Task A, blocked on the API key.
- Writing into `docs/STATUS.md` — draft the entry per §6.8, do not write it.

## Do NOT touch
- `backend/app/services/ml_postprocess.py` — no edits of any kind.
- `backend/app/services/translation.py` — Task A's file. Do not move the normaliser call
  inside `_translate()` or `_translate_async()`. Wrapping happens at the call sites in
  `ai.py` only, so the function signatures stay unchanged (AGENTS.md §5.3, §10).
- The two Malayalam-to-English `_translate_async()` call sites — their output is English;
  normalising it is pointless and would be a behaviour change nobody asked for.
- The six log sites fixed on 2026-08-27 (`main.py`, `translation.py`,
  `ai.py`, `relevance.py`). Do not re-introduce any patient text into a log line, and do
  not add a new log line that prints translated text (AGENTS.md §5.6).
- `backend/run_ml_postprocess_test.py` — run it, do not edit it.
- `docs/STATUS.md`, `docs/MASTER_PLAN.md`, `.agents/CURRENT_TASK.md`, `.agents/DECISION.md`.
- Any other file in the repo. If a fix seems needed elsewhere, halt and report it.

## Execution route
- B — Claude Code loop
- Why: route C test point 1 fails — the three call sites are NOT already named by a
  reliable line number (the 2026-08-23 numbers are stale after the 2026-08-27 edit), so
  locating them is a judgement step. Point 6 also fails: verifying Malayalam output is
  correct is not something a diff and an exit code can settle.
- Close-out: route B — never automated. Committing, pushing and opening the PR is
  `close-task`, developer-driven, per AGENTS.md §6.11.

## Manual (developer does)
- [ ] Approve this task file before any code is written (AGENTS.md §6.3).
- [ ] Read the live Malayalam output in the verification evidence and confirm it is
      correct Malayalam — an agent checking its own Malayalam proves nothing, same
      reasoning as the Task B1 codepoint audit.
- [ ] Approve the STATUS.md draft entry.
- [ ] All of close-out: commit, push, PR, merge.

## Agent (does on its own, once scope is confirmed)
- [ ] Locate every `_translate_async(` call site in `backend/app/api/v1/endpoints/ai.py`
      and report each one with its current line number, its source language and its
      target language. Expected: five sites total, three English-to-Malayalam, two
      Malayalam-to-English.
- [ ] Add the import of `normalise_malayalam` to `ai.py`, matching the existing import
      style in that file (AGENTS.md §8).
- [ ] Apply `normalise_malayalam()` to the returned string at the three
      English-to-Malayalam sites only.
- [ ] Run `python backend/run_ml_postprocess_test.py` and paste the full raw output.
- [ ] Run the live smoke test in `## Verification required` and paste the full raw output.
- [ ] Draft the STATUS.md entry per §6.8. Do not write it into the file.
- [ ] Run `code-review` at the end and produce the §12.13 seven-section report.

## Blocked on developer input
- [ ] None at run time. The one open question — whether to wire now given that
      `sarvam-translate:v1` triggers none of the three rules — is answered in this file:
      wire now, because Google Translate is the live provider and is the untested
      fallback path the normaliser was written to defend.

## Order
### Steps inside this task
1. Read `AGENTS.md`, `docs/STATUS.md` and this file fresh.
2. Locate and report all five `_translate_async(` call sites with current line numbers
   and language directions. If the count is not five, or the English-to-Malayalam split
   is not three, HALT under §12.5 condition 3 — do not guess which sites to wire.
3. Add the import.
4. Wrap the three English-to-Malayalam results.
5. Run `python backend/run_ml_postprocess_test.py` — must still be 26 passed, 0 failed.
6. Check nothing is listening on port 8000, kill it if so, start the backend, confirm it
   responds (AGENTS.md §5.9).
7. Run the live smoke test. Paste raw output.
8. Run `code-review`. Produce the §12.13 report.
9. Draft the STATUS.md entry. Do not write it.
10. Regenerate the repomix snapshot by overwriting the existing output file in place
    (AGENTS.md §6.9).

### Where this task sits
- Before this: nothing. Task B1 landed as PR #11.
- After this: §1.3a Task A (Sarvam client + Google fallback + circuit breaker), still
  blocked on the Sarvam API key. Then Task C (Redis translation cache, Opus tier).

## Verification required before this is considered done
- [ ] `grep -n "_translate_async(" backend/app/api/v1/endpoints/ai.py` — full raw output,
      pasted before any edit, showing every call site and its current line number.
- [ ] `python backend/run_ml_postprocess_test.py` — full raw output, `26 passed, 0 failed`,
      `EXIT CODE: 0`. Proves the module still behaves as it did at PR #11.
- [ ] Port 8000 confirmed free before starting the backend, and the backend confirmed
      responding, with the command output for both pasted.
- [ ] One live `/chat-stream` request with `language="ml"` against the local `hospital_ai`
      database, using synthetic patient text only. Paste the raw request and the raw
      response. The Malayalam reply must render correctly and must contain no ഡോ.
      abbreviation and no untranslated "Dr"/"Dr.".
- [ ] Evidence that the wrapper actually runs, not just that the app still works. If no
      rule fires on live Google output, say so explicitly and additionally prove the wiring
      by a throwaway scratch script that feeds a known rule-triggering string through the
      exact wired code path. A scratch script is fine (§12.4 whitelist); it is not
      committed.
- [ ] One live `/chat-stream` request with `language="en"` — the English reply must be
      unchanged, proving the English path is untouched.
- [ ] `git status --short` — full raw output, showing only `ai.py` modified and no other
      tracked file changed.
- [ ] No claim of "works" or "verified" anywhere in the report without the raw output
      pasted directly above it (AGENTS.md §5.10).

## Flags (AGENTS.md rule triggers)
- §5.3 — real risk of restructuring. Putting the call inside `translation.py` would be
  cleaner-looking and is forbidden here: it would change behaviour for the two
  Malayalam-to-English sites too, and it collides with Task A's file. Call sites only.
- §5.6 — this code path carries patient-facing text. No new log line may print translated
  or patient text. All verification text must be synthetic.
- §5.8 — three neighbouring pieces of work are deliberately excluded: formal pronouns,
  per-hospital config, and the untranslated-English-on-failure bug.
- §5.9 — needs the backend dev server on port 8000. Check and kill before starting.
- §5.10 — every claim needs pasted raw output.
- §12.5 condition 3 — halt if the `_translate_async` call-site count or language split
  differs from five total / three English-to-Malayalam.
- §12.5 condition 2 — halt if the work turns out to need a signature change in
  `translation.py`.
- Not a §5.1 concern: this is a pure text-in/text-out transform with no query, no
  `hospital_id` filter and no tenant-scoped data. It does change output for every tenant
  equally, which is why the route is B and not C.
- Not a §5.2 concern: the behaviour is uniform across all tenants, not clinic-specific.
- Not a §5.5 concern: no new legal or medical wording. The normaliser rewrites a title
  form, it does not author text.

## Suggested review tier (set at scoping time)
- Sonnet 5, medium effort — AGENTS.md §10 names "translation logic" in the Sonnet 5 list.
  No Opus trigger is expected: no query, no `hospital_id` filter, no migration, no
  logging change, no `services/security.py`, no signature change, no disclaimer wording,
  no `backend/research/` boundary, no auth or Redis keys, no `DATABASE_URL`.
  If the agent layer comes back naming Opus, that is a signal something in the diff went
  beyond this scope — do not accept a quiet upgrade without asking what triggered it.

## Suggested Antigravity model
- The default agentic coding model — ordinary feature work, no Opus trigger expected.
  Keep Antigravity on its included model; the Claude review layer is the safety net.