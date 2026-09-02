# Current Task

## Feature
A Claude Code `Stop` hook (`.agents/hooks/halt_answerer.py`) that fires when Claude
Code halts under AGENTS.md §12.5, reads `.agents/LOOP_HANDOFF.md`, and dispatches a
tool-restricted, headless `claude -p` answerer that may write `.agents/DECISION.md`
automatically for a narrow set of halt conditions — removing the developer from the
middle of cheap, mechanical halts without giving away any real decision.

## Plan reference
Not in MASTER_PLAN.md. Unplanned agent-tooling work. Follows the Antigravity scoped
command grant (PR #22, merged `8080da0`) and the governing-doc corrections (PR #21,
merged `1357752`). Both confirmed on `origin/main` 2026-09-02 via `git log`.

Branch: `feat/unattended-halt-loop`, cut from `origin/main` by the developer.

## How the answerer must behave

**Model and billing.** The answerer runs Sonnet on the developer's Claude Pro
subscription via `claude -p`. AGENTS.md §12.12 needs NO edit — Sonnet is already the
permitted tier for loop-driver-level work. `ANTHROPIC_API_KEY` must be unset; if set,
`claude -p` bills API credits instead of the subscription.

**Hard cost guard (added at scoping).** Before dispatching anything, the hook checks
`os.environ` for `ANTHROPIC_API_KEY`. If it is set, the hook writes nothing, dispatches
nothing, and exits — leaving the halt exactly as it would be with no hook installed.
This needs its own test case.

**Tool restriction.** The answerer may use only read-type tools needed to inspect
`.agents/LOOP_HANDOFF.md` and files it references, and may write exactly one file:
`.agents/DECISION.md`. No Bash. No git. No other write path.

**Per-condition behaviour — this is the safety-critical core:**

- **§12.5 conditions 1, 2, 5** (any Alembic migration; any §10 Opus trigger; anything
  under AGENTS.md §9 "When In Doubt") — the hook must never dispatch the answerer.
  It exits, leaving `LOOP_HANDOFF.md` for the developer. No exceptions, no flags.

- **§12.5 condition 3 (scope change)** — one-way door. The answerer may only ever
  answer "stay in scope: do not touch anything outside the `## Files/areas in scope`
  list; report the needed change instead." It may NEVER authorise a scope change.
  A scope widening is always the developer's.

- **§12.5 condition 4 (same error hit three times)** — one fixed answer, no reasoning
  about the error itself:
  > "Do not attempt a fourth time. Skip this step, record it as blocked in the
  > end-of-task report, and continue from the next step in `## Order` that does not
  > depend on it. If every remaining step depends on it, stop and report."

- **§12.5 condition 6 (fails the §12.4 reversibility test)** — the answerer is a
  false-positive filter, NOT an approver. It independently re-runs §12.4's four-part
  reversibility test against the handoff. It may write `DECISION.md` only if all four
  come out true, i.e. the original halt was a false alarm. If any one is false, it
  writes nothing and the halt stands for the developer.

**Halt-cycle budget.** An auto-answered halt counts toward AGENTS.md §12.12's
three-halt cap exactly like a developer-answered one. Auto-answers spend tokens too.

**Exit code.** The hook exits 0 in every path. On a `Stop` hook, exit code 2 means
"do not stop, keep going", which is not the signal wanted here — resumption is driven
by `DECISION.md` being newer than `LOOP_HANDOFF.md` (§12.7), not by the hook's exit
code. Verified against Claude Code hooks reference, 2026-09-02.

## Files/areas in scope
- `.agents/hooks/halt_answerer.py` — new.
- `.agents/hooks/run_halt_answerer_test.py` — new. Standalone runnable script, no
  pytest, matching the `backend/run_*_test.py` convention in spirit. Deliberately
  placed beside the hook rather than under `backend/`: this is agent tooling, not
  production backend code.
- `.claude/settings.json` — new or edited. Registers the `Stop` hook. Committed
  deliberately (not `settings.local.json`), matching how `.claude/skills/` is already
  tracked.
- `.agents/AGENTS.md` — exactly three edits, no others:
  - **§12.10** — add a bullet banning any dispatch from passing
    `--dangerously-skip-permissions` or any equivalent bypass flag. Recorded as
    found-NOT-fixed in `docs/STATUS.md` Catch-up 2026-09-01; this closes it.
  - **§12.10a** — add the `--add-dir <repo-root>` requirement. Without it, relative
    paths resolve against no grant and every allow rule silently fails. Proved
    empirically 2026-09-02, already recorded in STATUS.md prose.
  - **§12.15** — add a narrow exception permitting the halt-answerer (not Claude
    Code, not Claude Chat) to write `.agents/DECISION.md` automatically, for
    conditions 3 (stay-in-scope only), 4 and 6 only.
- `docs/MASTER_PLAN.md` — one append to §9 (Unplanned / Ad-hoc Work).

## MASTER_PLAN.md update
- [ ] Append to §9, dated 2026-09-02: "Unattended halt loop. Added a Claude Code
      `Stop` hook (`.agents/hooks/halt_answerer.py`) that dispatches a tool-restricted
      Sonnet answerer to auto-write `.agents/DECISION.md` for AGENTS.md §12.5
      conditions 3 (stay-in-scope only), 4 and 6. Conditions 1, 2 and 5 always halt for
      the developer. Three AGENTS.md edits: §12.10 bans bypass flags, §12.10a requires
      `--add-dir`, §12.15 narrows the DECISION.md write exception. Scope:
      `.agents/hooks/`, `.claude/settings.json`, `.agents/AGENTS.md`."

Pre-approved at scoping per §12.15 — no second gate when this step is reached.

## Do NOT touch
- Any file under `backend/` or `frontend/`. This task contains no product code.
- `backend/google_credentials.json` — separate, unresolved security item (tracked in
  git since `d2b2828`, key revocation outstanding). Not this task.
- Any AGENTS.md section other than the three named above.
- `MASTER_PLAN.md` §1.3a's "Close-out for every task above is manual" paragraph.
- `~/.gemini/antigravity-cli/settings.json` — developer-edited only, per §12.10a.
- The untracked files currently in `git status` and unrelated to this task:
  `.claude/launch.json`, `backend/mock_test.py`, `backend/test_welcome.py`,
  `cleanup.md`, `scratch_token_volume.py`, `test_httpx_leak.py`,
  `test_relevance.py`, `test_req.py`. Leave every one untouched.
- `.agents/DECISION.md`, `.agents/DECISIONS_TAKEN.md`, `.agents/LOOP_HANDOFF.md`,
  `.agents/REPORT.md`, `.agents/RUN_REPORT.md` — leftovers from the closed-out PR #21
  task. The developer deletes these by hand; the agent layer must not.
- `.agents/CURRENT_TASK.md` and `.agents/DECISION.md` as governing files (§12.15).

## Execution route
- B — Claude Code writes, developer reviews.
- Close-out: manual. Commit, push and PR are `close-task`, developer-driven, per
  AGENTS.md §6.11. No loop runner opens or merges a PR for this task.

## Manual (developer does)
- [ ] Delete the five leftover `.agents/` files listed above, then confirm.
- [ ] Confirm `ANTHROPIC_API_KEY` is unset in the environment that actually runs the
      hook — this is the condition the entire cost design rests on.
- [ ] Approve this task file (AGENTS.md §6.3).
- [ ] Approve the STATUS.md draft entry.
- [ ] All of close-out: commit, push, PR, merge.

## Agent (does on its own, once scope is confirmed)
- [ ] Read `AGENTS.md`, `docs/STATUS.md` and this file fresh from disk.
- [ ] Read the CURRENT text of §12.10, §12.10a and §12.15 off disk before editing.
      Do not rely on any copy pasted into a chat transcript.
- [ ] Write the hook and the test script.
- [ ] Register the hook. Make the three AGENTS.md edits. Append MASTER_PLAN §9.
- [ ] Draft the STATUS.md entry per §6.8. Do not write it.
- [ ] Regenerate the repomix snapshot in place (AGENTS.md §6.9).

## Order
1. Read `AGENTS.md`, `docs/STATUS.md` and this file fresh.
2. Read §12.10, §12.10a and §12.15 off disk. Present the exact proposed replacement
   wording for all three. STOP and wait for developer confirmation before any code.
3. Write `.agents/hooks/halt_answerer.py`.
4. Write `.agents/hooks/run_halt_answerer_test.py`. Must include, at minimum: a case
   per §12.5 condition 1–6; the `ANTHROPIC_API_KEY`-set refusal; the condition 3
   one-way door (assert it can never emit a scope widening); the condition 6 filter
   rejecting a case where one of the four reversibility parts is false.
5. Run the test script. Paste full raw output and exit code.
6. Register the `Stop` hook in `.claude/settings.json`.
7. Make the three AGENTS.md edits.
8. Append the MASTER_PLAN.md §9 entry.
9. Capture every item under `## Verification required`.
10. Run `code-review`. Produce the §12.13 seven-section report.
11. Draft the STATUS.md entry. Do not write it.
12. Regenerate the repomix snapshot in place.

## Verification required before this is considered done
- [ ] `git status --short` — full raw output. Paste it, do not summarise (§5.10).
- [ ] `git diff --stat` showing exactly the in-scope files and nothing else. If any
      `backend/` or `frontend/` file appears, HALT under §12.5 condition 3.
- [ ] `run_halt_answerer_test.py` full raw output and exit code.
- [ ] Evidence that the hook is actually registered and fires: the `/hooks` menu
      listing it, or a live `Stop` event showing it ran.
- [ ] A live end-to-end run: a real halt written to `LOOP_HANDOFF.md` under a
      condition 4 scenario, showing `DECISION.md` written with the fixed answer.
      Paste the resulting `DECISION.md` in full.
- [ ] A live negative run: a halt under condition 2 (any §10 Opus trigger), showing
      NO `DECISION.md` was written and the halt was left for the developer.
- [ ] Evidence the `ANTHROPIC_API_KEY` guard fires: set it, trigger a halt, show
      nothing was dispatched and nothing written.
- [ ] `git diff .agents/AGENTS.md` — full raw output, showing only the three intended
      edits and no other section changed.
- [ ] No claim of "works", "passes" or "verified" anywhere without the raw output
      pasted directly above it (§5.10). A description of what output said is not
      the output.

## Flags (AGENTS.md rule triggers)
- §5.1 / §5.2 — no query, no `hospital_id`, no tenant-specific behaviour. None apply.
- §5.3 — real restructuring risk in the AGENTS.md edits. Three sections, named
  explicitly. Any fourth section touched is a §12.5 condition 3 halt.
- §5.5 — no legal, medical or disclaimer wording is authored anywhere in this task.
- §5.6 — `LOOP_HANDOFF.md` may reference evidence files. The answerer must never
  copy raw patient text into `DECISION.md`. §12.6 already bars it from handoffs.
- §5.8 — one feature. The bypass-flag ban and the `--add-dir` rule are included
  because both are prerequisites for the loop being safe to run unattended at all,
  not as bundled extras.
- §5.10 — every claim needs pasted raw output.
- §12.5 condition 3 — halt if any file outside `## Files/areas in scope` needs
  touching, including a fourth AGENTS.md section.

## Suggested review tier (set at scoping time)
- Sonnet 5, medium effort. Mechanically, no §10 Opus trigger fires: no query, no
  `hospital_id` filter, no migration, no logging of patient text, no
  `services/security.py`, no function signature change, no disclaimer wording, no
  `backend/research/` boundary, no auth or Redis session keys, no `DATABASE_URL`.
- Noted separately, NOT a tier upgrade: this task widens what an automated process
  may do without the developer, and edits the document that governs the review
  layer. §10 does not list that as a trigger, so the tier stays Sonnet 5 per the
  mechanical rule. The developer may choose to review it harder anyway.
- If the agent layer comes back naming Opus, ask what triggered it rather than
  accepting a quiet upgrade.
