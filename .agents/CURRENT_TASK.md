# Current Task

## Feature
Add ten design tokens to the Tailwind v4 `@theme` block in `frontend/src/index.css` — ripple/wash colours, two elevation steps, a panel blur radius, and three motion values — with no consumer.

## Plan reference
Not in MASTER_PLAN.md. Unplanned frontend design work, same class as the four IRIS design entries already in §9 (2026-08-31, 2026-09-03 ×3). STATUS.md state at time of scoping: PR #25/#28 landed 25 `iris-*` tokens; PR #29/#30 rebuilt the widget and page shell as the first consumers; STATUS.md names Task C (Redis translation cache) as next up for Phase 1, so this is out of sequence. Developer confirmed at scoping that design work stays ahead of Task C.

## MASTER_PLAN.md update
- [ ] Append a dated entry to `## 9. Unplanned / Ad-hoc Work`: "IRIS design token addendum — ripple, elevation, motion. Ten tokens added to the `@theme` block in `frontend/src/index.css`. Nothing consumes them; the consumer is a later task." Append only; do not edit or renumber any section.

## Files/areas in scope
- `frontend/src/index.css` — the `@theme` block only. Add ten custom properties. Change nothing else in the file.
- `docs/MASTER_PLAN.md` — the §9 append above, and nothing else.
- `.agents/REPORT.md` — the end-of-task report, per AGENTS.md §12.20.

## Explicitly out of scope
- Any component consuming any of the ten tokens. That is the next task.
- The question of whether `iris-*` tokens belong in a global `@theme` block at all. Real, but it needs its own decision and its own diff.
- Renaming any existing token, including the `--radius-iris` / `--radius-iris-sm` asymmetry already recorded as deliberate.
- Amending AGENTS.md §12.10a to scope its port-clearing sentence explicitly to Antigravity. Logged as a follow-up; §5.8 keeps it out of this diff.
- Design frame 07 (`[TRANSLATION_UNAVAILABLE]`), which needs a change to the shared `useHospitalChat` hook.
- The `@ricky0123/vad-web` voice-detection init failure and the `vite.config.js` HMR overlay suppression from PR #30.

## Do NOT touch
- `frontend/src/themes/iris-hospitals/Chat.tsx`
- `frontend/src/themes/iris-hospitals/ChatMessage.tsx`
- `frontend/src/themes/iris-hospitals/index.tsx`
- `frontend/src/themes/iris-hospitals/AnimatedIntro.tsx`
- `frontend/src/hooks/useHospitalChat.tsx`
- `frontend/index.html`
- `frontend/vite.config.js`
- `frontend/tailwind.config.js` — not read under Tailwind v4; editing it does nothing and misleads the next reader
- `package.json` — add no dependency
- Any of the 25 existing `iris-*` properties. They must come back byte-identical in `git diff`.
- Anything under `backend/`
- Any Alembic migration. Run no alembic command.

## Execution route
- B — Claude Code loop
- Why: route-C test point 6 fails — reporting which tokens are reachable as Tailwind utilities versus custom-property-only is a judgement the agent must reason about and report, not a diff plus an exit code. Point 3 also engages §5.9 (dev server on port 5173).
- Close-out: route B — never automated to merge

## Manual (developer does)
- [x] Approve this task file as written, including the ten values below. Done at scoping.
- [ ] Approve the drafted STATUS.md entry before it is written (§12.15).
- [ ] Merge the PR. Never the agent's, ever.
- [ ] Re-upload `docs/MASTER_PLAN.md` to the Claude Project after merge, because the §9 append will have changed it.

## Agent (does on its own, once scope is confirmed)
- [ ] Read the whole `@theme` block in `frontend/src/index.css` off disk and paste it into the report. Count the properties. Do not grep for the substring `"iris-"` — `--font-malayalam`, `--radius-iris`, `--radius-iris-sm` and `--shadow-iris` do not contain it and the count will come back 19, not 25.
- [ ] Confirm the count is 25. If it is not, STOP and report before editing.
- [ ] Add exactly these ten properties, grouped, one short comment per group:
      `--color-iris-wash-a: #DCE9FA;`
      `--color-iris-wash-b: #EDF3FB;`
      `--color-iris-ripple-line: rgba(42, 105, 181, 0.05);`
      `--color-iris-panel: rgba(255, 255, 255, 0.62);`
      `--shadow-iris-raised: 0 1px 2px rgba(28, 36, 48, 0.06);`
      `--shadow-iris-float: 0 12px 40px rgba(28, 36, 48, 0.16);`
      `--blur-iris-panel: 22px;`
      `--motion-iris-fast: 160ms;`
      `--motion-iris-enter: 420ms;`
      `--motion-iris-ease: cubic-bezier(0.22, 0.8, 0.3, 1);`
- [ ] Clear port 5173 and start the frontend dev server, per §5.9. Developer decision at scoping (see `## Flags`) assigns this to Claude Code rather than the developer. Check the listener first, kill it if present, start the server, and confirm it responds before reading any computed style from it. Paste the raw output of the port check, the kill if one was needed, and the server's ready line.
- [ ] Run the verification below and paste every raw output.
- [ ] Report which of the ten are reachable as Tailwind utility classes and which resolve only as plain CSS custom properties. This determines how the consumer task must be written.
- [ ] Draft the STATUS.md Catch-up entry per §6.8. Do not write it.
- [ ] Append the §9 entry to `docs/MASTER_PLAN.md` — already approved via this file.
- [ ] Write the full end-of-task report to `.agents/REPORT.md`, per §12.20.
- [ ] Regenerate the repomix snapshot in place, per §6.9.

## Blocked on developer input
- [x] Palette — answered at scoping: the two wash colours stay blue, derived from `--color-iris-primary` #2A69B5. Purple was considered and rejected; it would require moving `--color-iris-primary` too, repainting every bubble and button, and is a different, larger task.
- [x] Third ripple colour — answered at scoping: deliberately omitted. The third blob reuses the existing `--color-iris-accent-surface` (#EAF2F2) rather than declaring a near-duplicate token.

Both answered before run time. Neither may be reopened by the agent.

## Order
### Steps inside this task
1. Agent reads and pastes the `@theme` block; confirms 25 properties.
2. Agent adds the ten properties.
3. Agent clears port 5173 and starts the frontend dev server, pasting the port check and the ready line.
4. Agent runs verification and pastes all raw output.
5. Agent appends the §9 MASTER_PLAN.md entry.
6. Agent drafts the STATUS.md entry and stops for approval.
7. Agent writes `.agents/REPORT.md` and regenerates the repomix snapshot.
8. `code-review` runs; its report returns to Claude Chat.

### Where this task sits
- Before this: nothing. PR #25, #28, #29 and #30 are all merged.
- After this: the consumer task — ripple background, translucent panel, seamless top bar, scroll-reveal on messages, in `Chat.tsx` and `index.tsx`. Scoped separately once the utility-reachability answer from step 4 is known.

## Verification required before this is considered done
- [ ] `npm run build` exits 0. State explicitly in the report that this proves compilation only. Tailwind v4 silently generates nothing for a class referencing a missing token; this project already hit that false negative once (STATUS.md Catch-up 2026-09-03, third entry).
- [ ] A temporary scratch element is added to a real scanned source file (`frontend/src/main.tsx`) using classes that reference the new tokens. Tailwind's JIT only generates CSS for classes found in scanned source. Injecting classes via the browser console produces a false negative and has already done so on this project.
- [ ] Computed styles read off the live dev server, raw values pasted. Expected:
      `bg-iris-wash-a` -> `rgb(220, 233, 250)`
      `bg-iris-wash-b` -> `rgb(237, 243, 251)`
      `bg-iris-panel` -> `rgba(255, 255, 255, 0.62)`
      `shadow-iris-raised` -> `0px 1px 2px 0px rgba(28, 36, 48, 0.06)`
      `shadow-iris-float` -> `0px 12px 40px 0px rgba(28, 36, 48, 0.16)`
- [ ] For any of the ten with no matching Tailwind utility namespace — expected for `--color-iris-ripple-line`, `--blur-iris-panel` and the three `--motion-iris-*` — confirm each resolves via `getComputedStyle(document.documentElement).getPropertyValue('<name>')` and paste the raw string.
- [ ] The scratch element is fully reverted and confirmed absent from the final `git diff`.
- [ ] `git diff frontend/src/index.css` shows all 25 pre-existing properties byte-identical.
- [ ] `git status --short` shows only `frontend/src/index.css`, `docs/MASTER_PLAN.md` and `.agents/REPORT.md` as modified. Anything else is a §12.5 condition 3 halt.

## Flags (AGENTS.md rule triggers)
- §5.2 — the `iris-*` prefix is one hospital's brand name in a global `@theme` block. This task adds ten more, taking the total to 35. It does not create the problem and deliberately does not fix it, but it deepens it. Needs its own decision, flagged not actioned.
- §5.9 — verification requires the frontend dev server on port 5173. Port must be checked and cleared first.
- §12.10a interpretation, developer decision at scoping — §12.10a's closing sentence "Port-clearing stays a manual, developer-performed step" sits inside the section governing Antigravity's `command(...)` grant, and its stated reasoning is about permission-pattern PID scoping in that file. Dev servers do not appear in §12.10's list of Claude Code's hard limits. The developer decided at scoping that Claude Code starts the dev server for this task. This reading is defensible but the rule text is ambiguous; amending §12.10a to scope that sentence explicitly to Antigravity is logged as a follow-up and is out of scope here.
- §5.10 — `npm run build` alone is not evidence. Computed styles from a live server are.
- §12.5 condition 3 — most likely halt: any file changed beyond the three named above.
- §12.5 condition 6 — second most likely: a design judgement not covered by the ten fixed values.
- No §5.1, §5.3, §5.4, §5.5, §5.6, §5.7 or §9 database trigger. No query, no migration, no logging, no patient text, no signature change, no non-local environment.

## Suggested review tier (set at scoping time)
- Sonnet 5, medium effort — no §10 Opus trigger fires. This sits between §10's Haiku list ("renaming a variable within a single file") and its Sonnet list ("new config fields"); rounded up per §10's "if unsure, name the higher one". A Haiku tier coming back from the agent layer is worth flagging, not accepting.

## Suggested Antigravity model
- The default agentic coding model — ordinary config-field work, no Opus trigger, ten fixed values already named.
