# Meta WhatsApp patient welcomes

Implementation uses one shared Arogya sender. Staff enter a mobile number, select English or Malayalam, confirm that the patient agreed, preview the approved copy and submit explicitly. The message identifies the hospital and links to its public patient assistant. Bulk sending remains the separate legacy Twilio flow.

## Current activation status

Disabled by default. No real Meta account readiness, approved template, public portal origin, deployment, live delivery or applied migration is asserted by this change. Local evidence uses synthetic fixtures, a disposable SQLite database and mocked Meta HTTP responses. The additive migration is a draft for review.

## Developer setup

1. Create or confirm your Meta business portfolio and developer app with the WhatsApp product. Register the shared Arogya sender and complete the ownership, display-name/business verification and billing steps Meta requests for your account. Do not delete/migrate an existing WhatsApp account as part of this task.
2. Generate and securely store an appropriate system-user access token with WhatsApp messaging access to the registered sender. Choose a currently supported Graph API version from your Meta console; do not copy the synthetic v99.0 test value. Keep all credentials in backend/deployment secret settings, never frontend environment variables, Git or reports.
3. Approve the exact English and Malayalam wording with the hospital/platform owner, then obtain Meta approval for the templates. Each template uses precisely two numbered BODY parameters: {{1}} is the hospital name; {{2}} is its full public assistant URL. Headers, media, dynamic buttons and named parameters are outside this first integration. Meta's approved category determines message charges; a generic welcome may be marketing. No production welcome or disclaimer wording has been fabricated in the code.
4. Copy backend/.env.example's META_WHATSAPP_* configuration to your private secret settings. Set each template name, exact approved BODY text and language code (defaults en_US and ml; match your approved template exactly). Supply the access token, numeric phone number ID, supported version, app secret and a separate webhook verify token. Generate a separate random WHATSAPP_RECIPIENT_HASH_SECRET of at least 32 characters. Keep that hash secret stable while requests may be replayed.
5. Set PUBLIC_PATIENT_BASE_URL to the deployed HTTPS origin only, with no path/query, and META_WHATSAPP_ENABLED_HOSPITAL_SLUGS to a comma-separated allowlist. Open /p/{slug} for every enabled hospital and verify its correct public theme/assistant; not every database hospital has a designed patient portal. The server resolves names and links using the authenticated hospital. No patient number is placed in the URL.
6. Review migration 7a8b9c0d1e2f, whose parent is the existing WhatsApp-log revision 0c682ef81de1. It adds nullable metadata and unique keys, preserving historical rows and twilio_sid. Obtain separate migration-application approval for the exact confirmed local target. Hosted schema changes and deployment are developer actions or require their own exact-target authorization. Deploy code only after the schema is ready, because the extended ORM also reads these columns in legacy paths.
7. Configure a publicly reachable HTTPS callback at <backend-origin>/api/v1/whatsapp/webhook. In Meta, use the separately configured verify token and subscribe the app/account to the messages webhook field. GET verification returns the challenge; POST requires X-Hub-Signature-256 validated against raw bytes with the app secret. The numeric sender ID must match. Callback processing uses stored provider message IDs for hospital ownership.
8. Set META_WHATSAPP_ENABLED=true only for an authorized test rollout. Send both language templates solely to a developer-controlled recipient explicitly authorized for this test. Verify actual arrival from Arogya, the correct hospital link, and callback-driven delivered/read state. Only then authorize patient use. Set the feature flag false to stop new welcomes; authenticated callbacks continue reconciling messages already in flight.

The Uvicorn callback access records are suppressed to avoid recording the GET verification token. Configure the reverse proxy/hosting access logs to omit verification query strings too; this application cannot control external proxy logs. Do not enable debug HTTP body logging.

## API and delivery behavior

All hospital APIs require the existing signed JWT with matching hospital_id and a staff subject; there is no cross-hospital superadmin override.

- GET /api/v1/hospitals/{hospital_id}/whatsapp/welcome-config returns enabled state and approved previews without secrets.
- POST /api/v1/hospitals/{hospital_id}/whatsapp/send-welcome accepts phone, language (en or ml), consent_confirmed (true), and request_id (UUID). It returns internal message_id, masked_phone, language, status and a sanitized error_code. Indian mobile input is normalized to +91; international input needs a country code. No free text or client-supplied link/sender is accepted.
- GET /api/v1/hospitals/{hospital_id}/whatsapp/messages/{message_id} reads only that hospital's Meta message state.

An identical request_id and normalized phone/language/permission within a hospital returns the existing result without a second send, even if sending is later disabled or templates, hospital name or portal settings change. A changed payload returns conflict. Database uniqueness protects concurrent submissions. The UI retains the same key for an unchanged form after a lost network response, disables simultaneous submissions and clears consent/language for the next recipient. This is per-intent duplicate prevention, not a permanent ban on messaging the same patient on a later authorized visit.

Pending/accepted/sent are not delivery confirmation. Delivered/read come from signed callbacks. Automatic checks run every five seconds for at most two minutes; staff can then refresh manually. Unknown means Meta may have accepted a timed-out or malformed submission; there is no automatic provider POST retry. Do not create another send for an uncertain message. Changing the phone or language starts a new intent, so only do so after investigating the previous one.

A crash between persisting pending and storing the provider ID can leave a pending row without a usable ID. The existing request key still prevents a duplicate send, but delivery cannot then be inferred or matched from a recipient number. Investigate in Meta before deliberately starting another request. A callback arriving before ID persistence returns retryable 503 when a recent pending/unknown send exists; unknown IDs with no recent send are ignored. Provider event timestamps are stored separately from local submission time. Equal-second sent/failure events resolve to failure; duplicate/late callbacks cannot undo delivered/read evidence. Incoming patient text is ignored and neither logged nor stored; this task does not provide a WhatsApp inbox or AI replies inside WhatsApp.

Only masked phone, keyed request/actor hashes, permission timestamp, language, provider ID and sanitized status codes are retained for new welcomes. Never retain or publish provider bodies, recipient numbers or secrets as verification evidence.

## Verification and references

From backend, run python run_meta_whatsapp_test.py in an environment with the declared dependencies. It forces a disposable SQLite connection and does not contact Meta. From frontend, run npx vitest run src/pages/Messaging.test.tsx, npm run build and npm run lint. Record existing repository lint failures separately from the scoped files; no unrelated lint cleanup is part of this task.

- [Meta's official Cloud API collection](https://www.postman.com/meta/whatsapp-business-platform/overview)
- [Meta template message payload example](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/messages/template/)
- [WhatsApp pricing and message categories](https://whatsappbusiness.com/products/platform-pricing/)
- [WhatsApp template management](https://whatsappbusiness.com/blog/manage-message-templates-whatsapp-business-api/)

Confirm version availability, permissions, billing and onboarding requirements against the account's current Meta console before activation. Account-specific access, template category/approval and live delivery remain developer inputs.
