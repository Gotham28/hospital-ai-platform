# Current Task

## Feature
Enforce tenant ownership on the six mutation endpoints identified in the 2026-08-08
isolation audit, so no authenticated user can modify or delete another hospital's rows.

## Plan reference
No dedicated MASTER_PLAN section — audit-derived fix from STATUS.md "Tenant-isolation
audit (2026-08-08)". Adjacent to §1.5 but distinct from it (§1.5 covers embedding-search
fallthrough and a context-building assertion; this covers endpoint authorization).

## Branch
Cut from origin/main per AGENTS.md §6.10:
    git fetch origin
    git checkout -b fix/tenant-ownership-mutation-endpoints origin/main
Do NOT cut from local main. Do NOT commit or push to main.

## Files/areas in scope
- `backend/app/api/v1/endpoints/ai.py` — `PATCH /knowledge/entry/{id}` (~line 1127) and
  `DELETE /knowledge/entry/{id}` (~line 1143): currently depend only on `get_db`. Add the
  auth dependency AND the ownership comparison. These two are unauthenticated writes to
  any tenant's KnowledgeBase — highest severity of the six.
- `backend/app/api/v1/endpoints/lab_tests.py` — `DELETE /{id}` (~line 42) and
  `PATCH /{id}` (~line 142): `_tenant` is injected via `get_current_tenant` but never
  compared to `db_item.hospital_id`. Add the comparison.
- `backend/app/api/v1/endpoints/medicines.py` — `DELETE /{id}` (~line 42) and
  `PATCH /{id}` (~line 148): same defect, same fix.

Reference implementation already in the codebase: `approve_appointment` in
`appointments.py` (~line 190). Reuse this exact pattern and its status code; do not
invent a new one.

## Decided behaviour
- Superadmin bypass: PRESERVED, matching `approve_appointment`. A superadmin may mutate
  any hospital's rows. Non-superadmin users are restricted to their own hospital.

## Explicitly out of scope
- Fixing anything found in the wider access-path sweep below — report only, separate diff.
- The `JWT_SECRET` fallback in `deps.py:10` — real issue, separate task (§5.8).
- MASTER_PLAN §1.5 proper (embedding fallthrough, context assertion, `system_prompt`
  wiring) — separate task.
- Refactoring the shared ownership check into a common dependency or helper — that is a
  structural change (§5.3); propose it, don't do it.
- Any Alembic migration. This task requires no schema change; if one appears to be
  needed, stop and ask.

## Do NOT touch
- No restructuring of `ai.py` — edit only inside the two named route bodies (§5.3).
- No signature changes to any existing function.
- No changes to `appointments.py` — it is the reference, not a target.
- No changes to `deps.py`, `get_current_tenant`, or the JWT fallback secret.
- No changes to GET/list endpoints, even if they look similarly exposed — report them
  under the sweep instead.
- No frontend changes unless a call is proven broken by the new auth dependency; if one
  is, stop and report before editing.
- Do not open the pull request. Report and stop.

## Manual (developer does)
- [ ] Confirm local `DATABASE_URL` points at the local `hospital_ai` DB, not Neon (§4).
- [ ] Open the PR, review, and merge.

## Antigravity (does on its own)
- [ ] Apply the `approve_appointment` ownership pattern to all six endpoints.
- [ ] Add the missing auth dependency to both `/knowledge/entry/` routes.
- [ ] Verify no error response leaks the other tenant's data — a 404 vs 403 distinction
      can itself confirm a row's existence. Match `approve_appointment` and state which
      it uses.
- [ ] Sweep and REPORT ONLY (do not fix): raw SQL, CRUD helpers in `app/crud/`, and bulk
      upload routes, for the same fetch-by-PK-then-mutate defect. The 2026-08-08 audit
      only checked `.query(<Model>)` call sites. Output a table matching that audit's
      format.
- [ ] Confirm `KnowledgeBase.tsx` still functions against the now-authenticated routes.

## Blocked on developer input
- None. All decisions resolved.

## Verification required before this is considered done
Per AGENTS.md §5.10: paste full raw output. Do not summarise. Do not write "verified".

- [ ] For each of the six endpoints: the actual post-fix code showing the ownership
      comparison. Six code blocks, not a summary sentence.
- [ ] Real request/response output showing a user authenticated to hospital A is REJECTED
      when targeting a row owned by hospital B — at least one endpoint per file
      (`ai.py`, `lab_tests.py`, `medicines.py`). Use the seeded multi-hospital local data
      and local-only superadmin from the 2026-08-09 catch-up.
- [ ] Output showing the same request SUCCEEDS for the owning hospital — proving the fix
      did not simply break the endpoints.
- [ ] Output showing a superadmin request SUCCEEDS across hospitals, confirming the
      bypass was preserved.
- [ ] Output showing both `/knowledge/entry/` routes now reject an unauthenticated
      request.
- [ ] `git diff --name-status origin/main...fix/tenant-ownership-mutation-endpoints` —
      three dots, against origin/main, to confirm no unrelated commits rode along.
- [ ] State explicitly which `DATABASE_URL` every command ran against.
- [ ] Confirm no Alembic migration was generated or applied.

## Flags (AGENTS.md rule triggers)
- §5.1 / §4 — modifies tenant-scoped access to KnowledgeBase, LabTest, Medicine. Primary.
- §10 Opus trigger — adds `hospital_id` filters; edits paths returning tenant data.
- §5.3 — touches `ai.py`; restructuring explicitly forbidden above.
- §5.8 — six endpoints across three files, one coherent feature. Sweep is report-only for
  this reason.
- Out-of-sequence — precedes §1.3 and §1.4, which STATUS.md lists as next up. Accepted.
- No §5.4 trigger — no migration expected.
- No §5.5 / §5.6 triggers — but any new rejection log must not include row contents.

## Suggested review tier
- Opus 5, high effort.

## Suggested Antigravity model
- Gemini 3.1 Pro. A wrong ownership check here is a silent data-leak path.