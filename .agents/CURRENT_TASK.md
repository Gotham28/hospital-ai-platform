# Current Task

## Feature
Add authentication and tenant-ownership enforcement to
`POST /hospitals/{hospital_id}/doctors/bulk-upload`, which currently creates Doctor rows
for any hospital_id with no auth dependency at all.

## Plan reference
No dedicated MASTER_PLAN section. Derived from the access-path sweep performed during the
2026-08-11 tenant-ownership task. Same defect class as the `/knowledge/entry/` routes fixed
in commit 9915c7f — unauthenticated write access to tenant-owned data. Adjacent to §1.5,
distinct from it.

## Branch
    git fetch origin
    git checkout -b fix/bulk-upload-tenant-auth origin/main
Do NOT cut from local main. Do NOT commit or push to main.

## Files/areas in scope
- `backend/app/api/v1/endpoints/hospitals.py` — the doctors bulk-upload route (~line 197).
  Confirm the exact current line and paste the route verbatim before editing; line numbers
  have drifted repeatedly in this repo.

Reference implementation: `approve_appointment` in `appointments.py` (~line 171), and the
six endpoints fixed in commit 9915c7f. Reuse that exact pattern and its status codes.

## Decided behaviour
- Add `_tenant: int = Depends(get_current_tenant)` and
  `token_data: dict = Depends(get_token_payload)`.
- Reject with 403 when a non-superadmin's token hospital_id does not match the
  `hospital_id` path parameter. Superadmin bypass PRESERVED.
- The check compares the PATH PARAMETER, not a fetched row — this route creates rows rather
  than mutating one, so there is no row to read ownership from. Check before any DB write.
- 404/403 split matches the existing convention. Do not normalise. Do not "improve" it.

## Explicitly out of scope
- The two `doctor_availability.py` findings from the sweep — they already check ownership
  correctly and are the accepted oracle pattern, not this defect class.
- The `JWT_SECRET` fallback in `deps.py:10` — separate task.
- The duplicate `CryptContext` in `auth.py:17` — report-only, separate task.
- Normalising the 404/403 enumeration oracle across all seven endpoints — separate task.
- Refactoring the shared ownership check into a helper — propose it, don't do it (§5.3).
- Any Alembic migration. None expected; if one appears needed, stop and ask.

## Do NOT touch
- No restructuring of `hospitals.py` — edit only inside the named route body.
- No signature changes to any existing function beyond adding the two dependencies.
- No changes to `deps.py`, `get_current_tenant`, or `appointments.py`.
- No changes to the six endpoints fixed in 9915c7f.
- No frontend changes unless a call is proven broken by the new auth dependency; if one is,
  stop and report before editing.
- Do not open the pull request. Report and stop.

## Manual (developer does)
- [ ] Confirm local `DATABASE_URL` points at local `hospital_ai`, not Neon (§4).
- [ ] Open the PR, review, and merge.

## Antigravity (does on its own)
- [ ] Paste the current route verbatim with its real line number before editing.
- [ ] Add both dependencies and the ownership check.
- [ ] Identify and report every frontend caller of this route and whether it sends a token.
- [ ] Sweep and REPORT ONLY: any other route accepting a `hospital_id` path/body parameter
      and writing to the DB without comparing it to the caller's tenant. Table format
      matching the 2026-08-08 audit.

## Blocked on developer input
- None.

## Verification required before this is considered done
Per AGENTS.md §5.10: paste full raw output. Do not summarise. Do not write "verified".
Use real `/auth/login` tokens — do NOT mint tokens with `create_access_token`.
Fixtures: `backend/seed_local_test_users.py` (gitignored, local only) creates
admin1@local.test (hospital 1) and admin2@local.test (hospital 2), password admin123.

- [ ] Post-fix code of the route, showing the ownership comparison.
- [ ] Unauthenticated request REJECTED (expect 401).
- [ ] admin1 (hospital 1) uploading to hospital_id=2 REJECTED (expect 403).
- [ ] admin1 uploading to hospital_id=1 SUCCEEDS.
- [ ] Superadmin uploading across hospitals SUCCEEDS.
- [ ] Confirm no Doctor rows were created by any rejected request — query and paste counts
      before and after.
- [ ] `git diff --name-status origin/main...fix/bulk-upload-tenant-auth` — three dots.
- [ ] State which `DATABASE_URL` every command ran against.
- [ ] Confirm no Alembic migration was generated or applied.

## Flags (AGENTS.md rule triggers)
- §5.1 / §4 — unauthenticated write path to tenant-owned Doctor rows. Primary.
- §10 Opus trigger — adds tenant-scoped auth path; touches auth dependencies.
- §5.3 — touches `hospitals.py`; restructuring forbidden.
- No §5.4 trigger — no migration expected.

## Suggested review tier
- Opus 5, xhigh effort — two or more Opus triggers fire (tenant-scoped write path plus auth
  dependency changes).

## Suggested Antigravity model
- Gemini 3.1 Pro. An unauthenticated write path to another tenant's Doctor table is the
  same severity class as the `/knowledge/entry/` defect.