# Current Task

## Feature
Close unauthenticated and cross-tenant access on 17 admin/internal API routes
across `hospitals.py`, `ai.py` and `appointments.py`, and stop the two
hospital-settings PATCH routes from copying arbitrary payload keys onto the
`Hospital` row.

Source: the 2026-09-15 full audit —
`.agents/runs/audit-2026-09-15-security.md` (SEC-01..04),
`.agents/runs/audit-2026-09-15-tenancy.md` (TEN-01, TEN-02) and
`.agents/runs/route-auth-inventory-2026-09-15.md` (Groups A and C). Every
Critical/High item used below was re-verified by Claude Code against the code
on 2026-09-15.

## Plan reference
Not one of the four items listed in `docs/MASTER_PLAN.md` §1.4 (Malayalam
injection patterns, SecurityLog, rejection message, rate limiting). Unplanned
security work, recorded via the §9 append below. It is a precondition for
§1.4 and §1.5 meaning anything: those harden the chat path while the admin
API is open.

Branch: `fix/lock-down-open-endpoints`, cut from `origin/main` (`948495f`,
PR #36) by the developer per AGENTS.md §6.10.

## Investigation findings (read-only, already done)

- **No router-level auth.** `backend/app/main.py:39-46` mounts every router
  with no `dependencies=`. Each route must guard itself.
- **Auth helpers** (`backend/app/api/deps.py`):
  - `get_current_tenant` (lines 22-37) returns the token's `hospital_id`, and
    returns `None` for a superadmin. A plain equality check against it
    therefore locks superadmins out — do NOT use it as the comparison source.
  - `get_token_payload` (lines 54-66) returns the full payload (`role`,
    `hospital_id`, `sub`).
  - `require_superadmin` (lines 50-52) — 403 unless `role == "superadmin"`.
- **Canonical tenant check already in the codebase** — reuse this exact shape
  (from `hospitals.py:213-216`, same as `appointments.py:134-138`):
  ```python
  user_role = token_data.get("role")
  user_hospital = token_data.get("hospital_id")
  if user_role != "superadmin" and str(user_hospital) != str(hospital_id):
      raise HTTPException(status_code=403, detail="Access denied. ...")
  ```
- **Frontend needs no change.** Every admin page calls through `api`, whose
  interceptor attaches the Bearer token (`frontend/src/api/axios.ts:13-16`).
  Only the patient chat hooks use bare `fetch`, and their routes stay public.
- `frontend/src/pages/Dashboard.tsx:48-52` PATCHes exactly three fields:
  `welcome_message`, `post_booking_disclaimer`, `relevance_criteria`.
- Nothing in `frontend/src` reads `google_sheet_id` from
  `GET /hospitals/slug/{slug}`; `ThemeLoader.tsx` uses only `id` and `name`.
- `create_appointment` and `get_appointment_status` have no Python callers
  (grep across `backend/`, excluding `venv/`) — reached only over HTTP.
  External HTTP callers (e.g. the separate WhatsApp Node app) are unknown;
  the developer accepted that risk on 2026-09-15.

## Files/areas in scope

### `backend/app/api/v1/endpoints/hospitals.py`
Unless stated otherwise, "check" = add
`token_data: dict = Depends(get_token_payload)` and the canonical check above,
placed before any DB write and before any other work.

1. `POST /` — `create_hospital` (line 81): add
   `_: str = Depends(require_superadmin)`.
2. `GET /` — `read_hospitals` (line 96): add `get_token_payload`. Superadmin
   → unchanged behaviour (all hospitals, existing `skip`/`limit`). Anyone
   else → only the hospital whose `id` equals the token's `hospital_id`
   (a list of 0 or 1).
3. `GET /{hospital_id}` — `get_hospital_by_id` (line 110): check.
4. `PATCH /{hospital_id}` — `update_specific_hospital` (line 121): check,
   plus replace the `setattr` loop with the role-based allowlist below.
   Keep the existing `_current_tenant` parameter; add `token_data`.
5. `PATCH /me` — `update_my_hospital_settings` (line 47): replace the
   `setattr` loop with the allowlist, using the hospital-admin set (a
   superadmin token has no hospital, so `/me` is a hospital-admin route).
6. `GET /slug/{slug}` — `get_hospital_by_slug` (line 64): remove
   `google_sheet_id` from the returned dict. Keep `id` and `name`. Route
   stays public.
7. `GET /{hospital_id}/doctors` — `get_hospital_doctors` (line 143): check.
8. `POST /{hospital_id}/doctors` — `add_doctor` (line 163): check.
9. `GET /{hospital_id}/billing` — `get_hospital_billing` (line 281): check.
10. `DELETE /{hospital_id}/doctors/{doctor_id}` — `delete_doctor`
    (line 314): check.
11. `PATCH /{hospital_id}/doctors/{doctor_id}` — `update_doctor`
    (line 323): check.
12. `DELETE /{hospital_id}/billing/reset` — `reset_hospital_billing`
    (line 373): add `_: str = Depends(require_superadmin)`. Superadmin only
    (developer decision, 2026-09-15).

**Allowlist (developer decision, 2026-09-15 — "by role"):** module-level
constants in `hospitals.py`.
- Hospital admin may set: `welcome_message`, `post_booking_disclaimer`,
  `relevance_criteria`.
- Superadmin may set: the three above, plus `name`, `address`,
  `system_prompt`, `google_sheet_id`, `is_active`.
- Nobody may set: `id`, `slug`, `created_at`, or any other key.
- Validate every payload key BEFORE any `setattr`. If any key is outside the
  caller's set, return 422 naming the rejected keys and write nothing.

### `backend/app/api/v1/endpoints/ai.py`
Checks must run before any OpenAI / embeddings call (cost).

13. `POST /ingest` — `ingest_knowledge` (line 296): check against
    `request.hospital_id`.
14. `POST /upload-pdf` — `upload_pdf` (line 314): check against the form
    `hospital_id`, before the file is read.
15. `GET /knowledge/{hospital_id}` — `list_knowledge` (line 1151): check.

### `backend/app/api/v1/endpoints/appointments.py`
Developer decision, 2026-09-15: include both.

16. `POST /` — `create_appointment` (line 64): check against
    `payload.hospital_id`, before any DB write. Update the "(Public)" comment
    at line 61 to say the route is now staff/admin-only.
17. `GET /status/{hospital_id}/{phone}` — `get_appointment_status`
    (line 263): check.

### New: `backend/run_endpoint_auth_test.py`
Offline, standalone, same shape as the existing `backend/run_*_test.py`
scripts (one `PASS`/`FAIL` line per check, a final `N passed, M failed`,
non-zero exit on any failure).
- Set `JWT_SECRET` to an obviously fake test value in `os.environ` BEFORE
  importing anything from `app` (`deps.py` reads it at import time). Mint
  test tokens with `jose.jwt` using that value and `HS256`.
- Use FastAPI `TestClient(app, raise_server_exceptions=False)` with
  `app.dependency_overrides[get_db]` returning a `MagicMock` session. No real
  database connection, no network, no OpenAI call (patch the module-level
  clients).
- For each of the 17 routes: (a) no token → 401; (b) hospital-admin token for
  hospital 2 targeting hospital 1 → 403; (c) the allowed caller (own-hospital
  admin, or superadmin for the superadmin-only routes) → status not 401/403.
  For superadmin-only routes also assert a hospital-admin token → 403.
- Plus: hospital-admin PATCH containing `system_prompt` → 422 and nothing
  set; hospital-admin PATCH with only the three Dashboard fields → not 422;
  `GET /hospitals/slug/{slug}` response has no `google_sheet_id` key;
  `GET /hospitals/` as a hospital admin returns only that admin's hospital.
- Synthetic fixtures only (§5.10). No real names or phone numbers.

### `.agents/CURRENT_TASK.md` — this file.

## Do NOT touch
- `backend/app/api/deps.py` — no new helper; inline the canonical check.
- `backend/app/api/v1/endpoints/auth.py`, and the JWT secret defaults
  (`deps.py:10`, `auth.py:13`, `config.py:30`) — that is task 2.
- Every other route in these files, including the patient-facing public
  routes that must stay open: `GET /ai/welcome/{hospital_id}`,
  `GET /ai/suggestions/{hospital_id}`, `POST /ai/chat-stream`,
  `POST /ai/chat`, `POST /ai/transcribe`, `POST /auth/login`,
  `GET /hospitals/slug/{slug}` (only its return dict changes).
- The 404-before-403 ordering in already-secured routes (TEN-03) — separate.
- How `add_doctor` / `update_doctor` handle their payload fields, beyond
  adding the check.
- Existing query filters — do not rewrite any `hospital_id` filter; only add
  the checks.
- Any file under `frontend/`.
- `docs/STATUS.md`, `docs/MASTER_PLAN.md` — written at close-out with
  developer approval.
- No Alembic migration — there is no schema change in this task.
- The untracked clutter already present in `git status` (`.design/`,
  `assets/`, `uploads/`, `.agents/REPORT.md`, `.claude/launch.json`,
  `.thumbnail`, `HANDOFF.md`, `backend/mock_test.py`,
  `backend/test_welcome.py`, `cleanup.md`, `deck-stage.js`,
  `docs/SECURITY_FIXES.md`, `scratch_token_volume.py`, `set_ml_welcome.sql`,
  `support.js`, `test_httpx_leak.py`, `test_relevance.py`, `test_req.py`).

## Execution route
B — Claude Code loop. Antigravity writes the code; Claude Code drives the
dispatch, runs the tests itself (Antigravity's §12.10a grant does not cover
the new script), and reviews.

## Manual (developer does)
- [ ] Cut the branch: `git fetch origin`, then
      `git checkout -b fix/lock-down-open-endpoints origin/main`.
- [ ] Approve this task file and place it at `.agents/CURRENT_TASK.md`.
- [ ] Separately, and now: revoke the Google service-account key in
      `backend/google_credentials.json`, and confirm `JWT_SECRET` is set
      wherever the backend is deployed.
- [ ] Before merge: check whether anything outside this repo (for example
      the separate WhatsApp Node app) calls `POST /api/v1/appointments/` or
      `GET /api/v1/appointments/status/...`. After this task they return 401
      without a staff token.
- [ ] Optional: against a local backend on port 8000 (§5.9 port check first),
      call one locked route without a token and paste the 401.
- [ ] Final review in Claude Chat (`review-skill`) at the tier below.

## Agent (does on its own, once scope is confirmed)
- Dispatch Antigravity with this file. The dispatch forbids any shell or
  `run_command` use.
- Run the new test script and the four existing offline scripts with
  `backend/venv/Scripts/python.exe`, and paste the full raw output.
- Run the four-lens `code-review` and write the report to `.agents/REPORT.md`.

## Order
1. Reset `.agents/DECISIONS_TAKEN.md` for this task (§12.4).
2. Dispatch Antigravity: `hospitals.py` items 1-12 and the allowlist,
   `ai.py` items 13-15, `appointments.py` items 16-17, and the new test
   script.
3. Read Antigravity's raw output. `git diff --stat` must show only the four
   in-scope code files, plus this file.
4. Run the new test and the four existing offline scripts; paste raw output.
   On failure, batch the fix into the next dispatch (at most three attempts
   at the same error, §12.5 condition 4).
5. Run the four-lens `code-review` and write the seven-section report to
   `.agents/REPORT.md`.
6. Draft the STATUS.md entry and stop for developer approval. Close-out per
   §6.11 only after approval.

## Verification required before this is considered done
- [ ] Full raw output of
      `backend/venv/Scripts/python.exe backend/run_endpoint_auth_test.py`,
      all PASS, covering all 17 routes and the allowlist, slug and list
      checks.
- [ ] Full raw output of `run_ml_postprocess_test.py`,
      `run_cors_config_test.py`, `run_rag_resilience_test.py` and
      `run_chat_stream_sentinel_test.py`, with pass counts unchanged from
      2026-09-15 (26, 10, 11, 8).
- [ ] `python -m compileall -q backend/app` — exit 0.
- [ ] `git diff --stat` — exactly `hospitals.py`, `ai.py`,
      `appointments.py`, `backend/run_endpoint_auth_test.py` and
      `.agents/CURRENT_TASK.md`.
- [ ] Grep evidence that each of the 17 route signatures now contains
      `get_token_payload` or `require_superadmin`.
- [ ] Grep evidence that no unrestricted `setattr(hospital, key, value)` loop
      remains in `hospitals.py`.

## Flags (AGENTS.md rule triggers)
- §10 Opus triggers fired: touches auth; adds and changes code paths that
  return tenant-scoped data (`read_hospitals` filtering, the checks); changes
  existing function signatures (17 route handlers gain a dependency
  parameter — no Python callers, verified by grep); touches routes that query
  `Doctor` and `Appointment` (their queries are not changed).
- §12.5 condition 2: the decisions this task needed (allowlist, billing
  reset, appointment routes, file scope) were answered by the developer
  in-session on 2026-09-15. Any further Opus-trigger decision not answered in
  this file → halt and ask.
- §5.1 multi-tenant isolation is the purpose of this task.
- §5.6: add no logging of request bodies. If a 401/403 is logged, log no
  payload.
- No migration. No disclaimer, legal or medical wording.

## Suggested review tier (set at scoping time)
- Opus 5, xhigh effort — several §10 Opus triggers fired in one diff: auth,
  tenant-scoped data paths, and function signature changes.

## Suggested Antigravity model
- Gemini 3.1 Pro (High) — developer's choice, 2026-09-15. Antigravity's
  Claude tiers are out of quota until about 2026-09-18. The standing rule
  would otherwise be Claude Opus 4.6 (Thinking) for Opus-tier work.

## MASTER_PLAN.md update
Append to `## 9. Unplanned / Ad-hoc Work` at close-out:

### 2026-09-15 — Lock down unauthenticated and cross-tenant admin routes
The 2026-09-15 full audit found 17 admin and internal routes in
`hospitals.py`, `ai.py` and `appointments.py` with no authentication or no
tenant check, and unrestricted field assignment in `PATCH /hospitals/{id}`
and `PATCH /hospitals/me`. Added the existing superadmin-or-same-hospital
check to each route, role-based field allowlists, superadmin-only hospital
creation and billing reset, and removed `google_sheet_id` from the public
slug response. Not one of §1.4's listed items; a prerequisite for them.
