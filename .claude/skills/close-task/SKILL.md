---
name: close-task
description: "Closes out a finished task on any project governed by an AGENTS.md rule file - checks the documentation is complete, sweeps for docs the task made stale, writes the approved STATUS.md entry, commits the scoped files, pushes the branch, opens the PR, records the real PR number and commit hashes back into STATUS.md, waits for CodeRabbit, and reports its findings back. Use this once review-skill has returned an accept verdict and the developer says to close it out - 'close this out', 'push it', 'open the PR', 'ship it', 'wrap this up', 'raise the PR'. Also use it in phase 2 when the developer pastes CodeRabbit's review back for triage. Do NOT use it while any review finding is still open - that is review-skill. Do NOT use it to scope new work - that is new-task. Do NOT use it to pause mid-task - that is pause-task. This skill never merges: merging is the developer's action, always, without exception."
---

# Close Task

Turns an accepted task into a pushed branch, an open PR, a STATUS.md entry that will still
be true in six weeks, and a CodeRabbit report the developer can act on. Produces exactly
one copy-pasteable Antigravity prompt per invocation.

---

## Project grounding — read this first, every time

This skill is project-neutral: it is installed once and used on every project. Everything
specific to a codebase comes from three files in that project's Claude Project, read fresh
each time.

| File | What it supplies |
|---|---|
| `AGENTS.md` | The standing rules (§5 non-negotiables), the working process (§6), and the review-tier lists (§10). Cited by number throughout this skill. |
| `STATUS.md` | What is actually done, in progress, and next. Changes often — never trust a remembered version. |
| `MASTER_PLAN.md` | Specs. Read only the section the current task belongs to. |
| `.agents/CURRENT_TASK.md` | The confirmed scope of the task in flight. |

Never restate a rule from memory, and never carry a rule over from a different project.
`hospital_id`, `tenant_id`, `user_id` and every other boundary are project-specific facts
that live in `AGENTS.md` §5.1 — read them there.

If `AGENTS.md` is not available in the conversation or the Project files, say so plainly
and ask for it before doing anything else. A review or a scoping pass with no rule file is
guesswork wearing a checklist's clothes.

If `AGENTS.md` exists but a section this skill cites is missing or renumbered, name the
mismatch and ask, rather than mapping it onto what you assume it meant.

---

## 0. Trigger boundary

Fire when **both** are true:

1. `review-skill` has returned `accept as-is`, or `accept after the follow-up below` **and
   the follow-up has been completed**.
2. The developer has said to close, push, or open the PR.

Do not fire if any review finding is still open. Do not fire if the developer has not
approved the STATUS.md draft. If either is missing, say which one and stop.

Do not fire on a pause. That is `pause-task`.

---

## 1. Output contract

Every invocation opens with this line, before anything else:

```
**close-task active — <task name> — phase <1|2> of 2**
```

Nothing above the banner.

| Phase | Output | When |
|---|---|---|
| 1 | Antigravity prompt: sweep, write STATUS.md, commit, push, open PR, backfill PR number and hashes, fetch CodeRabbit, report | Now |
| 2 | Triage of CodeRabbit's findings + a fix prompt, or a clean-to-merge statement | After the developer pastes CodeRabbit's review back |

Exactly one fenced prompt block per invocation. Never two.

---

## 2. Preconditions — refuse to close blind

Before writing the phase 1 prompt, confirm you have:

- The **approved** STATUS.md entry text, word for word. Not "the draft from earlier" — the
  version the developer signed off on. If it was corrected during review, use the corrected
  text.
- The **exact list of files** belonging to this task, from `.agents/CURRENT_TASK.md`
  `## Files/areas in scope`.
- The **branch name**, and confirmation it was cut from `origin/main`.

If any is missing, ask for that one thing and stop. Do not guess a file list.

### 2.1 What the approved entry must contain

An entry that records only "we did the thing" is worthless three sessions later, when
nobody remembers which branch it was on or whether anyone actually ran anything. Check the
approved text carries all six of these before you write the prompt:

| Field | What good looks like | Why |
|---|---|---|
| **Date + one-line summary** | `### Catch-up — 2026-08-22` then one plain sentence | So it can be scanned |
| **Branch name** | `branch fix/bulk-upload-tenant-auth` | The branch outlives your memory of it |
| **PR number** | `PR #7` — written as `PR: pending` at first, backfilled at §4 step 13 | Links the entry to the review |
| **Commit hashes** | Short hashes, every commit in the task | Lets anyone find the exact change later |
| **Verification: commands and their output** | The exact commands run, and what they printed | `AGENTS.md` §5.10 — a claim with no output is an assertion, not a report |
| **Deliberately deferred items** | What was left undone, why, and where it now lives | Stops a known gap becoming a forgotten gap |

Two rules about filling these in:

- **PR number and commit hashes cannot exist yet.** The PR is opened after the commit, and
  the commit hash is only known after committing. So the entry is written with literal
  `PR: pending` and `Commits: pending` placeholders, and §4 steps 13–14 replace them with
  the real values in a second, tiny commit. This is the only text Antigravity may change
  in the approved entry, and it may change nothing else in it.
- **Everything else missing is the developer's to supply.** If the approved entry has no
  verification output, or does not name the branch, **ask the developer for that one field
  and stop.** Do not write it yourself, do not infer it, and do not paste output that
  Antigravity produced but nobody checked.

### 2.2 Verification output that does not count

Reject the entry and ask again if the verification section says any of these and nothing
more:

- "Tested and working", "verified locally", "all tests pass" with no command and no output
- A summary of output instead of the output
- Output the coding agent claimed but could not have produced — for example test results
  from a headless run where shell commands were denied, so nothing was actually executed

If the task genuinely was not verified by running anything — a pure docs edit, say — the
entry should state that plainly: "No commands run; docs-only change." An honest "not
verified" is fine. An implied "verified" is not.

---

## 2a. Stale-docs sweep — do this before writing anything

A finished task very often makes some *other* line in the docs wrong. A bullet that said
"PR pending" for work that just merged. A plan row that still names a model the task
replaced. Nobody notices, because nobody is looking at those lines. This sweep is the
looking.

Before the STATUS.md entry is written, search for and list every place the docs now
contradict reality because of this task:

1. **`STATUS.md` current-state tables** — any row whose status this task changed.
2. **`STATUS.md` "Notes / Open Questions"** — any bullet describing this task's work as
   pending, unfixed, unresolved, or awaiting a PR.
3. **`MASTER_PLAN.md`** — any row, table cell, checklist item, dependency list or weekly
   plan line that names something this task changed. Search for the *old* value by name,
   not just the section the task was scoped to. A correction made in one section usually
   has a twin somewhere else.
4. **`AGENTS.md`** — file paths, function names or architecture facts the task changed.

Then split the findings in two, because they are staged differently:

| Where the stale line lives | What happens |
|---|---|
| `STATUS.md` | Fix it in this close-out. `STATUS.md` is the standing staging exception (`AGENTS.md` §6.11), so it may be edited and committed here. |
| `MASTER_PLAN.md`, `AGENTS.md`, or any other file | **Do not edit it.** It is outside the task's scope list, and `AGENTS.md` §5.8 (one feature per task) and §6.11 (stage only scoped files) both forbid folding it in silently. |

For anything in the second row: **stop and report it to the developer**, listing each
stale line with its file and section, and ask which they want — fold it into this task by
adding the file to `.agents/CURRENT_TASK.md` `## Files/areas in scope` first, or raise it
as a separate follow-up task. Then continue once they have answered.

If the sweep finds nothing, say so in one line. Do not invent findings to look thorough.

**Append-only logs.** If the project's `STATUS.md` declares a section append-only — a
"Catch-up" log, for example — never edit or delete an existing entry in it, even a wrong
one. Correct it by adding a new dated entry that says what changed. Editable sections such
as current-state tables and Open Questions bullets are not covered by that rule and should
be corrected in place.

---

## 3. What Antigravity may and may not do

| Action | Allowed | Note |
|---|---|---|
| Write the approved STATUS.md text | Yes | Approved text only, never its own wording |
| Correct STATUS.md table rows and Open Questions bullets this task made stale | Yes | §2a — STATUS.md is the standing staging exception |
| Edit an entry inside an append-only STATUS.md log | **No** | Add a new dated entry instead |
| Replace the `PR: pending` / `Commits: pending` placeholders | Yes | §4 steps 13–14, those two fields only |
| Edit `MASTER_PLAN.md`, `AGENTS.md`, or any other doc | **No** | Report the stale line and stop — §2a |
| Reset `.agents/CURRENT_TASK.md` to idle | Yes | `AGENTS.md` §6.9 — leave it uncommitted, it is not in the scope list |
| Regenerate any repo snapshot/index | Yes | Overwrite in place, never delete first |
| `git add` **named files only** | Yes | Never `git add -A`, never `git add .` |
| `git commit` | Yes | Scoped files only |
| `git push` to a **feature branch** | Yes | Never to `main` |
| Open a PR against `main` | Yes | A PR is a proposal, not a change |
| Read CodeRabbit's review via `gh` | Yes | Read-only |
| **Merge a PR** | **Never** | Developer only. No exception, ever. |
| Fix CodeRabbit findings | No | Needs developer approval per finding — phase 2 |
| Force-push, `git reset --hard`, delete a branch | No | Developer only |
| Push to `main`, or change branch protection | No | Developer only |
| Commit a file outside the task's scope list | No | Stop and report instead |

**Why merge is never autonomous:** CodeRabbit is a bot. If Antigravity opens a PR, reads a
bot's approval, and merges, then no human has looked at the change. The developer presses
merge.

---

## 4. Sequence the phase 1 prompt must impose

Order matters. Each step's output is checked before the next one runs.

1. `git status -sb` — confirm the working tree holds only expected changes
2. Run the stale-docs sweep (§2a) and paste the findings list. If anything outside
   `STATUS.md` is stale, **stop here and report** — do not continue to step 3
3. Write the approved STATUS.md entry, with `PR: pending` and `Commits: pending` left as
   literal placeholders
4. Correct the STATUS.md table rows and Open Questions bullets named in the step 2 sweep
5. `git diff <path to STATUS.md>` — paste it, to prove nothing else in that file changed
6. Stage the named files, one by one, by explicit path
7. `git status --short` — paste it, to prove staging matches the scope list
8. Commit
9. `git show --name-only HEAD` — paste it, to prove the commit holds only scoped files
10. `git rev-parse --short HEAD` — paste it, this is the hash the entry needs
11. `git branch --unset-upstream` if the branch tracks `origin/main`
12. Push to the feature branch
13. Open the PR against `main`, and paste the PR number the command returns
14. Replace `PR: pending` and `Commits: pending` in the entry with the real PR number from
    step 13 and the hash(es) from step 10. Change nothing else. Then
    `git diff <path to STATUS.md>`, paste it, stage `STATUS.md` alone, commit as
    `docs: record PR number and commit hashes`, and push
15. Reset `.agents/CURRENT_TASK.md` to idle and regenerate any repo snapshot. Leave both
    uncommitted — neither is in the scope list
16. Wait for CodeRabbit, then fetch and paste its review in full
17. Stop

**Step 11 exists because `git checkout -b <n> origin/main` silently sets the upstream to
`origin/main`.** A bare `git push` from such a branch targets main. Always include it.

**Step 14 exists because a STATUS.md entry saying "PR pending" is how a project ends up
with merged work that its own notes still describe as unfinished.** The placeholder must
not survive the close-out it was created in.

---

## 5. Staging rules

The working tree often holds unrelated uncommitted work. The commit must contain only this
task's files.

The prompt must state, always:

- Stage each file by explicit path. Never `git add -A`, never `git add .`, never
  `git add -u`, never a glob.
- If any file outside the scope list is modified, **do not stash, revert, restore or
  discard it.** Leave it alone and commit around it.
- If a file *in* the scope list is unexpectedly missing from `git status`, stop and report.
- Paste `git show --name-only HEAD` after committing. A commit whose contents were never
  shown is an unverified commit.

**`STATUS.md` stages whole.** `git add` takes the entire file, not just the new entry. So
before staging it, run `git diff` on it and read the result: if it contains changes beyond
the approved entry and the §2a sweep corrections, **stop, name exactly what those extra
changes are, and ask** whether to include them, commit them separately, or leave them.
Never decide that on your own, and never stash or discard them.

---

## 6. CodeRabbit handling

The prompt must tell Antigravity to:

- Open the PR, then wait for CodeRabbit to finish — it is not instant, so poll rather than
  assume
- Fetch the review with `gh pr view --comments`, and `gh api` for inline review comments
- Paste **every** CodeRabbit comment in full, including ones it disagrees with
- **Not fix anything.** Not one line. Reporting only.
- **Not resolve, dismiss, or reply to** any CodeRabbit comment
- Say plainly if CodeRabbit found nothing

Antigravity filtering CodeRabbit's output down to what it considers important defeats the
purpose of having a second reviewer.

---

## 7. Phase 2 — triaging CodeRabbit

When the developer pastes CodeRabbit's review back, sort every comment into:

- **Must fix** — a real defect, or anything touching an `AGENTS.md` §5 non-negotiable
- **Should fix** — a genuine improvement, safe and small
- **Ignore** — style opinion, false positive, or out of scope for this task

State plainly which of CodeRabbit's points you disagree with and why. A bot reviewing a
diff cannot see the task scope, so out-of-scope suggestions are expected and normal.

Then produce **one** fix prompt covering only the Must-fix and approved Should-fix items,
restating the scope limits and the Do NOT touch list. Anything deferred goes to STATUS.md
Notes / Open Questions — never silently dropped.

If a fix lands after the STATUS.md entry was written, its commit hash belongs in that
entry too. Say so, and name the hash to add — the entry's `Commits:` line should end up
listing every commit in the task, not only the first.

If nothing needs fixing, say so in one line and tell the developer the PR is ready for them
to merge. Do not pad a clean result.

---

## 8. Merge

Never in a prompt. Never suggested as something Antigravity could do. When the PR is ready,
tell the developer it is ready and list what they should do:

- confirm the STATUS.md entry now shows a real PR number and real commit hashes, not
  `pending`
- merge the PR
- delete the merged branch, local and remote
- re-upload `STATUS.md`, `MASTER_PLAN.md` and `AGENTS.md` to the Claude Project if any
  changed

The last one matters more than it looks. The Claude Project holds a copy, not a live link.
An un-reuploaded `STATUS.md` means the next session reviews against a version of reality
that stopped being true at this merge.

---

## 9. Plain language

Follow the Project's plain-language rule. Short sentences, common words, no term used
before it is explained. Keep exact file names, branch names, commit hashes and rule numbers
precise — simple wording, exact facts.
