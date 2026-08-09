# Current Task

## Feature
Migrate AROGYA staging database from Render Postgres to Neon Postgres (free tier),
preserving pgvector data, then delete the Render database once verified stable under
real usage.

## Plan reference
Not in MASTER_PLAN.md — unplanned, cost-driven work taken ahead of §1.3. STATUS.md may
have moved since this was last read live; re-check before treating this as current.

## Files/areas in scope
- `docs/neon_migration_runbook.md` — created and fully accepted (all 7 original items +
  the Step 3d referential-integrity fix)
- `DATABASE_URL` env var in Render's deployed environment — updated to Neon direct
  connection string (no code change was needed; Pass 1 confirmed `config.py` already
  reads it from the environment)
- `.agents/CURRENT_TASK.md` — this file itself; was accidentally wiped twice with no git
  history to restore from (see Flags)

## Explicitly out of scope
- Any schema change — host move only, confirmed in Pass 1
- WhatsApp send testing — deliberately excluded from the write-path verification, real
  Twilio side effects
- Neon connection pooler (PgBouncer) adoption — noted in the runbook as a separate future
  decision, not part of this migration

## Do NOT touch
- No `ai.py` or `services/` restructuring — unrelated to this task
- No other hospital's data — all testing scoped to `hospital_id=1`
- No further Render deletion action without explicit developer approval — irreversible

## Manual (developer does)
- [x] Create Neon project
- [x] Check Render DB size vs 0.5GB cap — 9550 kB, passes with large margin
- [x] Enable pgvector on Neon (`CREATE EXTENSION IF NOT EXISTS vector;`)
- [x] Obtain Neon direct connection string
- [x] Run `pg_dump` from local machine (PostgreSQL 18 client tools)
- [x] Run `pg_restore` into Neon
- [x] Update `DATABASE_URL` in Render deployment env, redeploy
- [x] Run live read-only smoke test
- [x] Authorize and run one live write-path test transaction
- [x] Suspend Render Postgres instance (not deleted) to stop billing during observation
- [ ] Delete test appointment `APT-D7E8A9` (hospital_id=1) from Neon
- [ ] Rotate Render DB password (was pasted in chat during this task)
- [ ] Rotate Neon DB password (was pasted in chat during this task)
- [ ] Observe a real usage session on Neon (real bookings, WhatsApp log writes, at least
      one hourly reminders-job cycle against real data — the authorized test write only
      proved the write path works, not sustained real traffic)
- [ ] Confirm `.dump` backup retention plan (currently one local copy at
      `D:\Hospital\neon-migration-dump\arogya_staging_render.dump`)
- [ ] Final decision + execution: delete Render database — separate sitting, irreversible

## Antigravity (does on its own, once scope is confirmed)
- [x] Pass 1 inspection (DATABASE_URL handling, Render coupling check)
- [x] Draft and fix `neon_migration_runbook.md` (7 items + Step 3d rework)
- [x] Add AGENTS.md §9 bullet: no commands against non-local databases without approval
- [x] Regenerate repomix snapshot after each accepted change
- [x] One explicitly authorized write-path test via the live API

## Blocked on developer input
- [ ] Get `.agents/CURRENT_TASK.md` under git tracking — waiting on: developer decision
      to commit it now and keep committing it going forward (see prevention plan below)
- [ ] Apply the drafted STATUS.md "Catch-up" entry — waiting on: developer approval of
      the exact wording

## Verification required before this is considered done
- [x] Step 3a–3f all passed with pasted output, both sides (Render/Neon) where applicable
- [x] Live read-only smoke test (`/welcome/1`, `/hospitals/1/doctors`) — 16 doctors
      matched pre-migration count
- [x] Live write-path test — appointment created and read back, correctly scoped to
      `hospital_id=1`
- [ ] A genuine full session of real (non-test) traffic against Neon
- [ ] Both exposed passwords rotated
- [ ] Explicit developer go-ahead for Step 5 (Render deletion)

## Flags (AGENTS.md rule triggers)
- §4/§9 — every DB-touching command required explicit developer approval with a
  confirmed target; followed throughout
- §5.10 — no unevidenced claims; enforced across every review round this task
- §5.8 — one feature/task at a time; documentation and execution phases kept separate
- §6.9 — this file was reset before the task was actually closed, with no git history to
  fall back on; this is the incident this recreation exists to fix

## Suggested review tier (set at scoping time)
Sonnet 5, medium — remaining open items are manual/developer actions (password rotation,
deletion) or a git-tracking fix, not Antigravity code work. If any future action in this
task touches Neon or Render again, that specific action escalates to Opus 5, high per
§10 (non-local database trigger).