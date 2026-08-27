---
name: drive
description: "Drives a scoped task through to a PR on any project governed by an AGENTS.md rule file. Classifies the pending diff by AGENTS.md section 10, then routes: Haiku tier work is done and closed out autonomously, Sonnet tier produces an Antigravity prompt and stops, Opus tier stops for a human. Use when the developer says 'drive this', 'take it from here', or runs the unattended runner. Never merges."
---

# Drive

Read `.agents/AGENTS.md` and `.agents/CURRENT_TASK.md` before anything else.
AGENTS.md section 5.10 applies throughout: paste the full raw output of every
command before any analysis. Output first, analysis after.

## Absolute limits

- Never merge a pull request. Ever. That is the developer's action (6.11).
- Never run an Alembic command or create a migration file (5.4).
- Never connect to any database that is not the confirmed local one (section 9).
- Never `git add -A`, `git add .`, or `git add -u`. Stage by explicit path only.
- Never restructure, refactor or clean up anything the task did not ask for (5.3).
- One feature per diff (5.8). If the tree holds unrelated changes, stop and say so.

## Step 1 - classify

Run and paste in full:

    git status --short
    git diff --stat

If the working tree contains changes belonging to more than one feature, STOP.
Report what you found and which files belong to which. Do not proceed.

If `CURRENT_TASK.md` names an execution route of B, or names a suggested review
tier of Opus 5, or has an unanswered item under `## Blocked on developer input`,
STOP. Those are human-gated by the task file itself.

Classify the pending work using AGENTS.md section 10 only. Emit exactly one line:

    TIER=<HAIKU|SONNET|OPUS> TRIGGER=<the single rule text that fired>

If unsure between two tiers, name the higher one (section 10, never round down).

## Step 2 - route

### HAIKU tier

Mechanical only: docs text, comments, formatting, STATUS.md wording, renaming a
variable inside a single file. If the work is more than that, reclassify.

1. Do the work yourself, scoped to the files named in `CURRENT_TASK.md`.
2. Run `/review-skill` on your own diff.
3. If and only if the verdict is accept, run `/close-task`: commit the scoped
   files by explicit path, push, open the PR against `main`. Do not merge.
4. If the verdict is anything else, write the findings to `.agents/handoff.md`
   and stop without touching git.

### SONNET tier

Do NOT write the code. Write `.agents/antigravity-prompt.md` containing:

- The exact files to change, with line numbers, and why each one.
- What is explicitly out of scope, as a "do not touch" list.
- The AGENTS.md rules that apply to this work, by number.
- The verification evidence required before it may report done, per 5.10.
- A closing instruction: do not commit, do not push, do not merge.
- The section 10 suggested review model line for the diff it will produce.

Then STOP. Tell the developer to run this to copy it:

    Get-Content .agents\antigravity-prompt.md -Raw | Set-Clipboard

### OPUS tier

STOP immediately. Write your classification, the trigger that fired, and what
you would look at to `.agents/handoff.md`. Report that a human must take this.
Do not write code. Do not write an Antigravity prompt.

## Step 3 - resume after Antigravity

When the developer says Antigravity is done:

1. Run `/review-skill` on the working tree diff.
2. If accept, run `/close-task`.
3. If not accept, write the findings and a corrected Antigravity prompt to
   `.agents/antigravity-prompt.md`, and stop.

## Step 4 - retry limit

Count rounds in `.agents/rounds.txt`. Create it with `1` on the first Antigravity
prompt written for the current task. Increment it each time a corrected prompt is
written for the same task.

If the count reaches 2 and the review still does not return accept, STOP. Do not
write a third prompt. Write to `.agents/stuck.md`: the task name, every finding
from both rounds, what changed between them, and your best guess at why the task
is not converging - usually the scope was too large or the task file is ambiguous.
Tell the developer the task needs rescoping, not another attempt.

Delete `.agents/rounds.txt` when a task closes out successfully.