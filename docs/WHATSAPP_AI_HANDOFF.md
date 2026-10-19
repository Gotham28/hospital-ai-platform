# Arogya WhatsApp integration: handoff for the next AI

Snapshot date: **2026-10-19, Asia/Calcutta**. This is a portable context document, not approval to activate production, apply a migration, or send messages. The user requested this file and authorised pushing it. No credentials or patient data belong here.

## Start here

Continue onboarding the user's **Meta WhatsApp Cloud API** integration. The application feature has already been built, reviewed, accepted, pushed and merged. **Do not rebuild it or tell the user to merge PR #43 again.** The immediate remaining work is Meta production-sender setup, approved templates, secure backend configuration, separately authorised schema/deployment work, and controlled integration testing.

The user prefers **simple, short, step-by-step instructions tied to their current screenshot**, with one small next action at a time. They have already received the broad setup checklist. Resume from the production-setup screen rather than repeating account creation or the test-message tutorial.

Suggested first reply:

> Your Meta test message is already working. Open **Basic setup → Step 2. Production setup** and show me that page with any access token hidden. Before changing the sender, tell me whether the number you want to use for Arogya already has WhatsApp or WhatsApp Business on it.

Do not assume later steps were completed in the time since the last update; confirm progress with the user.

## Goal and confirmed product decisions

- Hospital staff enter a patient's number in the hospital admin **Messaging** screen, select **English or Malayalam**, confirm the patient's permission, preview the approved message, and explicitly submit it.
- **No send on typing, blur, patient registration, appointment save, or merely entering a number.** Explicit form submit/Enter is the trigger.
- Use **Meta Cloud API**, not Twilio, for the new welcome flow.
- One **shared Arogya sender** serves permitted hospitals. The message identifies the hospital and includes its public patient-assistant web link.
- Send one selected language per patient, not both languages in one message. English is the initial/default language and resets between recipients.
- Show accepted/sent/delivered/read/failed/unknown states in the admin screen. API acceptance is not delivery confirmation.
- Legacy Twilio single/bulk contracts remain; bulk controls are separate. No automatic Twilio fallback for new welcomes.
- Two-way WhatsApp chat, AI replies inside WhatsApp, inboxes, campaigns, appointment reminders, registration-triggered sending and redesigns are outside this completed task. The link opens the existing web assistant.

## Current status and evidence boundaries

| Item | Known status |
|---|---|
| Application implementation | Complete and merged in PR #43 |
| Four independent source-review lenses | Final verdict accept as-is; developer accepted it |
| Meta app and test sender | Created/claimed in the user's Meta console, shown in screenshots |
| Meta test message to the user's phone | **User reported it arrived and worked** |
| Real Arogya sender | Not confirmed registered/ready |
| Intended sender already used by WhatsApp | Unknown; ask before changing or migrating it |
| Production access token, app secret, webhook verification token | Not supplied to this chat; current external configuration unknown |
| Approved English/Malayalam templates and exact text | Not supplied/confirmed |
| Public portal origin and allowed hospital slugs | Not confirmed |
| Migration application | Draft/offline evidence only; no application was performed in this chat |
| Live hospital-screen send and signed delivery callback | Not demonstrated |
| Feature flag | Code/example defaults to false; deployed environment was not inspected |
| Live rollout | Not authorised by the completed implementation/close-out approvals |

The successful Meta-console test was its provided sample template from Meta's test number. **It is not evidence that the real Arogya sender, either hospital welcome template, our backend, database schema or delivery webhook works end to end.** Do not describe it as production acceptance.

Last visible console navigation: **Connect on WhatsApp → Basic setup**, with **Step 1. Try it out**, **Step 2. Production setup**, **Step 3. Business verification**, and **Next steps**. Integration type was **Integrate with API**. The last screenshot had the test-number claim completed, Generate token, Recipient and provided test-message controls. The user then reported success twice. The assistant's last instruction was to open Step 2 and show that page. No later screenshot was received.

Do not copy the test Phone Number ID, test business-account ID, temporary token, or a version displayed in a test snippet into production settings without checking the real account. No screenshot values need to be recovered from this handoff.

## Repository and Git state verified for this handoff

- Repository: <https://github.com/Gotham28/hospital-ai-platform>.
- Feature PR: <https://github.com/Gotham28/hospital-ai-platform/pull/43>.
- GitHub reports **MERGED**, at `2026-10-12T14:04:51Z` (19:34:51 India time).
- Squash-merge commit on main: `9b1542f0ae98a9a6836d4fdc4776735c56c848f4`.
- Original implementation commit: `2546a1e338e34a1628596a87538a996b42025902`.
- Original STATUS PR/hash backfill commit: `830821722f2d9cb866aecb4944226e2cb7bbf239`.
- Original feature branch: `codex/meta-whatsapp-welcome`. Do not use its old base as the starting point for new application work.
- Fetched `origin/main` on 2026-10-19: `c533314` (research PR #44). The merged service contains `send_welcome` and `apply_statuses`; the core service/routes/model/migration/frontend/tests have no changes between the WhatsApp squash commit and this fetched main.
- Documentation-only branch carrying this file: **`codex/whatsapp-ai-handoff`**, created from fetched `origin/main`. If this document is not yet on main, fetch that branch or obtain this file directly. This document does not contain its own commit hash; use the branch history to resolve it.

Local Windows workspace details (useful only on this computer):

- Original checkout: `D:/Hospital/hospital-ai-platform`, on `feat/iris-ease-health-redesign`, ahead of its upstream with unrelated work and many dirty/untracked paths. **Do not push that checkout wholesale, stash, reset, clean, discard, or include unrelated files.** A deleted credentials file is also present in that unrelated status; do not restore or publish credentials.
- Existing isolated worktree: `C:/Users/aravi/.codex/worktrees/meta-whatsapp-welcome/hospital-ai-platform`. It now holds the documentation branch. Existing task-record/VAD build-file changes and untracked decision records were preserved and excluded from this documentation commit.
- `.agents/CURRENT_TASK.md` was reset to the idle placeholder after implementation close-out; that idle state is a local, uncommitted workflow record. A fresh checkout may instead contain an older committed task plan. Do not treat either an old approved implementation plan or this handoff as a new activation authorisation.
- The completed task and close-out report are also archived locally under `.agents/runs/meta-whatsapp/` in the isolated worktree. This directory is ignored and will **not** exist in a normal clone. Essential context is included here; committed raw implementation evidence is in `HANDOFF.md` and `docs/STATUS.md`.

This repo uses squash merges. Check content and GitHub PR state when establishing merge status, not whether original feature commit hashes are ancestors of main.

## Implementation map

Paths are repository-relative and available in the merged code:

| Path | Responsibility |
|---|---|
| `frontend/src/pages/Messaging.tsx` | Welcome form, language, permission, approved preview, request key, status polling/manual refresh; separate legacy bulk UI |
| `frontend/src/pages/Messaging.test.tsx` | 15 focused component cases in the accepted run |
| `backend/app/services/meta_whatsapp.py` | Configuration, phone parsing, approved template payloads, persistence/idempotency, Meta send and callback status transitions |
| `backend/app/api/v1/endpoints/whatsapp.py` | Additive authenticated welcome/config/status APIs alongside legacy handlers |
| `backend/app/api/v1/endpoints/whatsapp_webhook.py` | Public GET verification and raw-body-signed POST callbacks |
| `backend/app/main.py` | Webhook router and callback access-log token suppression |
| `backend/app/models/whatsapp_log.py` | Nullable Meta audit/provider/idempotency metadata, preserving legacy columns |
| `backend/alembic/versions/7a8b9c0d1e2f_meta_whatsapp_welcome.py` | Additive migration draft; parent `0c682ef81de1` |
| `backend/app/core/config.py`, `backend/.env.example` | Backend-only settings and blank/default-disabled examples |
| `backend/requirements.txt`, root `requirements.txt` | Runtime dependency declarations; root manifest is UTF-16 LE BOM: preserve its encoding |
| `backend/run_meta_whatsapp_test.py` | Standalone isolated backend evidence harness; 29 cases in accepted run |
| `docs/WHATSAPP_SETUP.md` | Detailed provider setup, template contract, rollout and incident behavior |
| `HANDOFF.md` | Full raw verification output and accepted four-lens review; historical pre-close-out snapshots are dated |
| `docs/STATUS.md`, `docs/MASTER_PLAN.md` section 9 | Approved implementation/close-out history and scoped ad-hoc roadmap append |

Relevant API contracts:

```text
GET  /api/v1/hospitals/{hospital_id}/whatsapp/welcome-config
POST /api/v1/hospitals/{hospital_id}/whatsapp/send-welcome
GET  /api/v1/hospitals/{hospital_id}/whatsapp/messages/{message_id}
GET  /api/v1/whatsapp/webhook
POST /api/v1/whatsapp/webhook
```

Send input is `phone`, `language` (`en` or `ml`), `consent_confirmed` (true), and `request_id` (UUID). The server resolves hospital, sender, approved copy and URL; do not introduce arbitrary client text or URLs. Hospital APIs require the existing signed JWT with matching hospital ownership and staff subject; there is no new cross-hospital superadmin bypass.

## Backend configuration checklist (no actual secrets)

Set private backend/deployment secrets, not frontend variables or committed files:

```dotenv
META_WHATSAPP_ENABLED=false
META_WHATSAPP_ACCESS_TOKEN=
META_WHATSAPP_PHONE_NUMBER_ID=
META_WHATSAPP_GRAPH_VERSION=
META_WHATSAPP_APP_SECRET=
META_WHATSAPP_VERIFY_TOKEN=
META_WHATSAPP_TEMPLATE_EN=
META_WHATSAPP_TEMPLATE_ML=
META_WHATSAPP_TEMPLATE_BODY_EN=
META_WHATSAPP_TEMPLATE_BODY_ML=
META_WHATSAPP_LANGUAGE_EN=en_US
META_WHATSAPP_LANGUAGE_ML=ml
PUBLIC_PATIENT_BASE_URL=
META_WHATSAPP_ENABLED_HOSPITAL_SLUGS=
WHATSAPP_RECIPIENT_HASH_SECRET=
```

- Access token must be appropriate for the real sender. Production should use suitable system-user credentials, not the temporary tutorial token. Confirm required messaging/management access for the actual asset and onboarding flow in current Meta documentation.
- Phone Number ID is Meta's numeric identifier, not the phone number itself and not the WhatsApp Business Account ID.
- Select a currently supported Graph version from the real account. Never use synthetic test value `v99.0`.
- App secret authenticates callback signatures. Verify token is a separate private random string that must match the callback configuration in Meta.
- `WHATSAPP_RECIPIENT_HASH_SECRET` is another independent random secret, at least 32 characters. Keep it stable across restarts and pending request replays; do not reuse JWT or Meta secrets.
- Template names, language codes and exact approved BODY text must match Meta's approved assets. Blank production text is deliberate; do not invent final welcome/disclaimer wording or silently translate it.
- Each language template must use exactly **two numbered BODY parameters**: `{{1}}` = hospital name, `{{2}}` = full assistant URL. Headers, media, dynamic buttons and named parameters are outside this first implementation. Meta determines the approved category; do not promise utility classification or a specific charge without checking current pricing.
- `PUBLIC_PATIENT_BASE_URL` is the deployed HTTPS **origin only**, without path/query. The server builds `/p/{encoded_hospital_slug}`. Use a comma-separated slug allowlist, and verify every actual hospital portal before enabling it. No patient phone goes into the URL.

## Migration, webhook and delivery details that must not be lost

1. Migration `7a8b9c0d1e2f`, parent `0c682ef81de1`, adds ten nullable Meta fields and unique hospital/request and provider-message keys. It preserves historical Twilio rows and `twilio_sid`. Do not recreate the original WhatsApp table or assume a fresh database.
2. New fields include provider message/request IDs, request fingerprint, language, permission timestamp/actor hash, safe error code, local status-update timestamp and **provider_event_at**. The provider clock is separate from local submission time.
3. **Schema must be ready before deploying the extended ORM**, including for legacy WhatsApp log callers. Read current migration graph/schema and obtain approval for the exact database target before any application. Previous approval covered drafting only.
4. Callback URL: `https://<actual-backend-origin>/api/v1/whatsapp/webhook`. Use the backend origin, not the frontend URL. Configure GET verification with the same verify token, subscribe the app/account to the `messages` field, and ensure the WhatsApp Business Account is subscribed to the app. Verify registration/subscription in the current console; a passed challenge alone does not prove live status events arrive.
5. POST verifies `X-Hub-Signature-256` against raw bytes with the app secret **before JSON parsing**, limits payloads to 1 MiB, checks the configured sender and derives hospital ownership from the stored provider message ID. Do not derive tenant identity from incoming phone or caller-provided hospital IDs.
6. Only masked phone, keyed hashes, permitted audit metadata, provider ID and sanitised status/error codes are retained. No raw recipient, patient text, tokens, provider bodies or callback payloads in logs/reports. Uvicorn callback access records are filtered; separately configure proxy/hosting logs to omit verification query strings.
7. Identical hospital/request key and phone/language/permission replays return the saved result, even after mutable setup changes or disabling sending. Changed payload with the same key conflicts. Persist pending before the provider call; uniqueness handles concurrent insertion. **No automatic provider-send retry.**
8. A timeout, malformed success, ambiguous persistence or missing provider ID may leave **unknown/pending**. Investigate in Meta before deliberately creating another send; changing recipient/language creates a new intent and can defeat duplicate protection. A callback before ID persistence may receive retryable 503; without a usable provider ID, some ambiguous sends cannot reconcile automatically.
9. Provider timestamps, duplicate and out-of-order callbacks are handled without undoing delivered/read evidence. Equal-second sent/failure resolves to failure. Repeated same-state events advance the provider clock. Preserve these fixes.
10. UI checks every five seconds for up to two minutes, then allows manual refresh. Slow/overlapping responses, old recipients and unmount must not overwrite newer status or block subsequent patients. Preserve cancellation, recipient-scoped counters and stale-response protection.
11. Disabling new welcomes does not disable authenticated callbacks reconciling in-flight messages. Incoming patient messages are ignored; this is not a WhatsApp chat bot/inbox.

## Verification already performed (historical, not rerun for this file)

Accepted fix-pass evidence dated **2026-10-11**, raw commands/output in `HANDOFF.md` and the **2026-10-12** STATUS catch-up entry:

- Backend: **29 passed**, synthetic settings/disposable SQLite, mocked Meta, dotenv reads suppressed before app imports. Includes both languages, permission/config, tenant isolation, real uniqueness insertion collision, replay after setup changes, sanitisation, uncertain sends, signed/challenge/sender/size callbacks, provider timing and legacy synthetic rows.
- Frontend: **15 passed**, including form submit events, no typing sends, language/permission, retries, double submit, slow/reversed responses, polling and recipient cleanup.
- Focused ESLint and TypeScript: exit 0. Production frontend build: exit 0.
- Full frontend lint: **exit 1, 64 problems (58 errors, 6 warnings)** in unchanged/out-of-scope files. Not fixed in this task. Do not claim the repository is lint-clean.
- Migration compiled offline for PostgreSQL. No schema upgrade took place. SQLite collision/historical-row fixtures are not deployed PostgreSQL migration acceptance.
- Component submit events are not physical-browser acceptance. Dependency declarations/import checks are not a fresh full dependency installation. No live bilingual hospital integration was tested.
- Four read-only Codex review lenses (scope, rules, evidence, blast radius) ended clean and the user accepted the verdict. Legacy review-tier taxonomy was Opus 5/xhigh, but actual execution/review used user-selected Codex; no Opus-model review occurred.
- CodeRabbit skipped automatic review because the repository had fewer than ten stars. The user explicitly chose **leave the PR without CodeRabbit review**. Do not call its green skipped check approval or post a trigger without permission.
- Supplemental close-out `git diff --check` found a trailing space at the then-current Messaging line 208. No formatting fix was applied during close-out; do not claim that line was proven pre-existing.

Useful repeat commands, after confirming scope and dependencies:

```text
# From backend/; harness forces synthetic settings, disposable DB and mocked Meta
python run_meta_whatsapp_test.py

# From frontend/
npx vitest run src/pages/Messaging.test.tsx
npx eslint src/pages/Messaging.tsx src/pages/Messaging.test.tsx
npx tsc --noEmit --jsx react-jsx --target ES2022 --module ESNext --moduleResolution bundler --esModuleInterop --skipLibCheck --types vite/client src/pages/Messaging.tsx src/pages/Messaging.test.tsx
npm run build
npm run lint
```

Do not assume the original machine's dependencies exist elsewhere. Backend runtime needs declared HTTPX and phonenumbers dependencies. The original run used shared Python 3.14 at `D:/Hospital/hospital-ai-platform/backend/venv/Scripts/python.exe`, temporary phonenumbers in `%TEMP%/meta-whatsapp-test-deps` via PYTHONPATH, and an ignored frontend node_modules junction. These are machine-specific, not a portable installation method. Build scripts copy tracked VAD assets and can change their line endings; do not commit those unrelated artifacts.

## Remaining work, in order

1. Confirm the user's current console screen and whether the intended sender is already on WhatsApp/WhatsApp Business. Continue **Step 2. Production setup**. Do not delete, migrate or unregister an existing account without a separate explicit decision.
2. Register/verify the real shared Arogya sender, complete account/display-name/business/billing requirements Meta actually requests, and confirm readiness. Prior test success does not answer these questions.
3. Obtain exact owner-approved English/Malayalam wording and Meta-approved templates using the required two body parameters. Record names/text/codes/category, not secrets.
4. Confirm the actual backend HTTPS origin, public patient origin, correct deployed `/p/{slug}` portals and initial hospital allowlist. Do not guess domains/slugs from localhost or a Vercel preview.
5. Configure credentials privately and keep sending disabled. Do not ask the user to paste secrets into chat or screenshots.
6. Separately scope/review and obtain exact-target authorisation for migration application and deployment. Inspect current migration heads and dependencies first; do not blindly run an upgrade command from a previous guide.
7. Configure/verify webhook challenge, account subscription, sender ID and actual signed status delivery.
8. Obtain explicit authorisation for a developer-controlled test recipient, temporarily enable an authorised test rollout, and test both approved welcomes through the **hospital admin screen**. Confirm real receipt, correct sender/hospital/language/link and callback-driven delivery state. A read receipt may depend on recipient settings; delivered is distinct from accepted.
9. Only after acceptance, authorise patient rollout with staff permission confirmation. Document evidence without numbers/secrets. If uncertain, disable new welcomes and investigate; do not resend automatically.

No patient rollout, hosted DB operations, migration, or real-recipient send is authorised merely by receiving this file, prior code review, merging PR #43, the successful Meta-console sample, or the user's permission to push this document.

## Workflow and guardrails for the next AI

Read root `AGENTS.md` (if present), canonical `.agents/AGENTS.md`, current user instructions and any applicable skills before changing code. Rules can change; this snapshot does not replace them.

Session-specific user decisions relevant to interpreting older project rules:

- Planning, decisions, review and close-out happen inside Codex, not a separate Codex Chat/Claude Chat relay.
- The executor is decided per task; the completed task explicitly used **Codex direct**, overriding older Antigravity-only/Sonnet-only wording for that task. Do not silently extend that exception to an unrelated task.
- All scoped implementation tenant/auth/logging changes and migration drafting were approved in the original task; actual migration application, deployment and live sends were not.
- Future implementation work needs a fresh scoped task and approval, using the repository's task/executor workflow. This document is a factual handoff, not a replacement approved CURRENT_TASK.
- Preserve strict hospital isolation and generic per-hospital configuration. No cross-hospital bypasses or hardcoded hospital IDs. No fabricated approved content. Keep research code separate and unrelated redesign work untouched.
- Collect real command output; distinguish historical evidence, user reports, source inspection and fresh execution. Don't invent passing checks or deployment status.
- Stage only explicitly scoped named files; no `git add -A`, `.`, `-u` or globs. Never merge a PR autonomously or push to main. Feature pushes need an explicit branch target; a branch created from origin/main initially tracks main, so remove that upstream before first push.
- Do not edit governance mid-task or bypass permission hooks. Previously identified AGENTS sections 2/3 omit the Meta architecture, and sections 12.1-12.3 contain older routing/executor language. The user approved deferring those updates to a separate documentation task.
- `PROJECT_NOTES.md` historically calls the old Twilio migration unapplied while STATUS records a prior local application. That discrepancy predates this feature; inspect the intended database only under the required authorisation rather than inferring current schema from either document.
- The user dislikes repeated approvals: reuse explicit authorisation already provided for the same action. Still respect concrete migration/hosted/real-send boundaries and required task-review gates. Explain any necessary approval with its actual rule/source.
- Bulk diffs/surveys and four-lens code reviews follow the user's delegation/context rules; don't re-read entire STATUS/MASTER_PLAN or the generated repomix snapshot. Read relevant sections.

The old `HANDOFF.md` includes statements such as acceptance/PR/STATUS pending. Those are historical pre-close-out records. The dated acceptance record, applied STATUS entry and verified merged PR state above supersede them for current status.

## References

- [Merged implementation PR #43](https://github.com/Gotham28/hospital-ai-platform/pull/43)
- [Setup guide](WHATSAPP_SETUP.md)
- [Committed implementation evidence and review](../HANDOFF.md)
- [Status history](STATUS.md) — WhatsApp section and Catch-up 2026-10-12 only
- [Meta's official Cloud API collection](https://www.postman.com/meta/whatsapp-business-platform/overview)
- [WhatsApp Business messaging policy](https://whatsappbusiness.com/policy/)

Meta UI, pricing, permissions, onboarding and API versions may change. Verify current official documentation/account screens before giving precise provider instructions. Do not assume an example, temporary test resource, or historical article is production configuration.
