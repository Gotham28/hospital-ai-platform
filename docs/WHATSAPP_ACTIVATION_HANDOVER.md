# WhatsApp welcome messages — activation handover

**For:** the employee activating Meta WhatsApp welcome messages for Arogya.
**Owner:** Gautam (owns every account below; grants access and signs off at the checkpoints).
**Written:** 2026-11-03.

## What you are switching on

Hospital staff open the admin **Messaging** screen, type a patient's mobile number, pick
English or Malayalam, tick that the patient agreed, and press send. The patient gets a
WhatsApp message from the **Arogya** sender with the hospital's name and a link to that
hospital's AI assistant page (`https://<patient site>/p/<hospital-slug>`). Delivery and
read ticks come back to the screen through a Meta webhook.

**The code is finished and already on `main`** (PR #43). You are not writing code. Your job
is account setup, configuration, one database migration and a controlled live test. The
engineering reference is [`docs/WHATSAPP_SETUP.md`](WHATSAPP_SETUP.md); this guide is the
practical, ordered version of it.

## Ground rules

1. **Never use Gautam's personal Facebook login.** You work from your own Facebook account,
   added to the company's Meta business portfolio. Sharing logins breaks 2FA and risks a
   Meta ban on the whole business.
2. **Secrets go only into Render's environment settings** (and a password manager if Gautam
   wants a copy). Never into Git, chat messages, screenshots, email or this file. Secrets
   here are: the access token, app secret, webhook verify token, recipient hash secret,
   the number's two-step PIN and the Neon database URL.
3. **Stop at every `CHECKPOINT`** and get Gautam's written OK before going past it.
4. **No real patient numbers** until Gautam signs off the final checkpoint. Test only with
   your own or Gautam's phone.
5. Keep `META_WHATSAPP_ENABLED=false` until Phase 7.

## Where things live

| Thing | Where |
|---|---|
| Company website (Meta verification, privacy policy) | `https://gothoslabs.com` |
| Patient pages + admin app (frontend) | Vercel project for `frontend/` |
| Backend API | Render: `https://hospital-ai-platform.onrender.com` |
| Database | Neon (hosted Postgres) |
| Webhook URL to give Meta | `https://hospital-ai-platform.onrender.com/api/v1/whatsapp/webhook` |
| Meta | business.facebook.com (portfolio) and developers.facebook.com (app) |
| Code | GitHub `Gotham28/hospital-ai-platform` |

---

## Phase 0 — Gautam grants access (Gautam does this, ~20 min)

Gautam: do these before handing over. Use the employee's own email/accounts. Everything can
be revoked when the work is done.

- [ ] **Meta business portfolio** — business.facebook.com → Settings → Users → People →
      Add people → employee's email → **Full control** (admin). Admin is needed for business
      verification and creating the system user. Then assign assets: the WhatsApp account
      and the app, both with full control.
- [ ] **Meta app** — developers.facebook.com → your app → App roles → Roles → Add people →
      **Administrator** → employee's Facebook account.
- [ ] **Payment method** — Business settings → WhatsApp accounts → the account → Payment
      settings → add the company card. **Gautam enters the card himself**; the employee
      never handles card details. Meta charges per template message sent.
- [ ] **Render** — dashboard → Workspace settings → Members → invite (needs Developer or
      Admin to edit environment variables).
- [ ] **Vercel** — the team that owns the Arogya frontend → Settings → Members → invite.
- [ ] **Neon** — console → Organization/Project → invite member.
- [ ] **GitHub** — repo Settings → Collaborators → add (Write is enough).
- [ ] **DNS for gothoslabs.com** — either invite the employee to the registrar/DNS provider,
      or plan to add one CNAME record yourself in Phase 2.
- [ ] **The spare SIM** — the employee needs it in hand to receive the verification
      SMS/call once in Phase 3. It must **not** be logged into WhatsApp or WhatsApp
      Business on any phone.

---

## Phase 1 — Company website ready for Meta (~1 hour)

Meta checks that the business is real and that the sender name "Arogya" belongs to it.
`gothoslabs.com` must show:

- [ ] The **legal business name exactly as on the registration documents** (GST, MSME/Udyam,
      incorporation or shop licence — whatever Gautam submits), plus address, phone and
      email. Mismatches are the most common rejection reason.
- [ ] A page or section naming **Arogya** as a Gothos Labs product (e.g. "Arogya — AI
      hospital assistant by Gothos Labs"). This is what lets the WhatsApp display name
      "Arogya" be approved under a business called Gothos Labs.
- [ ] A **privacy policy** at a stable URL (e.g. `https://gothoslabs.com/privacy`) that
      covers WhatsApp messages sent on behalf of hospitals and how phone numbers are handled.
      **Gautam writes or approves the wording** — do not copy a generic template and
      treat it as final.
- [ ] An email address on the gothoslabs.com domain helps (Meta can verify by domain email).

Then in Meta:

- [ ] developers.facebook.com → app → App settings → Basic: set Privacy Policy URL, App
      domain `gothoslabs.com`, category, app icon. Save.
- [ ] business.facebook.com → Settings → Security centre → **Start business verification**.
      Upload the documents Gautam provides, choose domain or phone verification. Approval
      takes from a day to a couple of weeks. Phases 2–5 can continue meanwhile.
- [ ] Optional but good: Business settings → Brand safety → Domains → add and verify
      `gothoslabs.com` (DNS TXT record).

---

## Phase 2 — Branded link for the patient pages (~30 min)

The message link must open the hospital's Arogya assistant page, which lives on the Vercel
app, not on gothoslabs.com. A `*.vercel.app` link in a business message looks like
phishing to patients and to WhatsApp's spam checks, so give the app a subdomain.

- [ ] **CHECKPOINT A** — confirm the subdomain name with Gautam. Suggested:
      `arogya.gothoslabs.com`.
- [ ] Vercel → Arogya frontend project → Settings → Domains → add `arogya.gothoslabs.com`.
      Vercel shows the DNS record to create (normally a CNAME to `cname.vercel-dns.com`).
- [ ] Add that record at the gothoslabs.com DNS provider. Wait until Vercel shows "Valid"
      and the HTTPS certificate is issued.
- [ ] Render → backend service → Environment → **`ALLOWED_ORIGINS`**: append
      `,https://arogya.gothoslabs.com` to the existing value (do not replace it). Without
      this, the patient chat on the new domain is blocked by CORS.
- [ ] Open `https://arogya.gothoslabs.com/p/<slug>` for each hospital to be enabled and
      confirm the right hospital's page and assistant load and chat works. Not every hospital
      in the database has a designed patient page — note which ones work.
- [ ] Write down the slugs that work. They become `META_WHATSAPP_ENABLED_HOSPITAL_SLUGS`.

---

## Phase 3 — Register the phone number (~30 min)

- [ ] developers.facebook.com → app → WhatsApp → API Setup → **Add phone number**.
- [ ] Display name: **Arogya**. Category: Medical & health. Fill the profile description
      and website (`https://gothoslabs.com`).
- [ ] Verify by SMS or voice call on the spare SIM.
- [ ] Set the **two-step verification PIN** when asked. Give it to Gautam for his password
      manager; you will need it again only if the number is re-registered.
- [ ] From the API Setup page, note (these are IDs, not secrets):
  - Phone number ID → `META_WHATSAPP_PHONE_NUMBER_ID`
  - WhatsApp Business Account ID (for your records)
- [ ] The display name goes into Meta review. Until it is approved, the number may be
      limited; that is expected.

Do **not** use the temporary access token shown on the API Setup page for anything except
quick experiments — it expires in 24 hours.

---

## Phase 4 — Message templates (~1 hour + Meta review)

Meta only allows business-started messages through pre-approved templates. We need **two**:
one English, one Malayalam, each with exactly two variables.

- `{{1}}` = hospital name (filled in automatically by the server)
- `{{2}}` = full assistant link (filled in automatically)

Rules that cause rejections:

- The body must **not start or end with a variable**. Put a sentence after the link.
- Body text only. No header, footer, media or buttons — the code does not send them.
- No URL shorteners, no all-caps, no promotional language if you want the Utility category.
- Use numbered variables `{{1}}` `{{2}}`, not named ones.
- Provide sample values when submitting, e.g. `Iris Hospital` and
  `https://arogya.gothoslabs.com/p/iris-hospital`.

Steps:

- [ ] Draft the English and Malayalam wording. Example **structure only** (not approved
      wording): *"Welcome to {{1}}. You can ask our assistant about doctors, timings and
      appointments here: {{2}} We look forward to helping you."* Do not promise
      anything the system cannot do — it ignores replies, so don't offer "reply STOP"
      or "reply to chat" unless Gautam arranges how that is handled.
- [ ] **CHECKPOINT B** — Gautam (and the hospital if he wants) approves the exact final text
      in both languages. Do not submit unapproved wording.
- [ ] WhatsApp Manager → Message templates → Create template.
  - Category: **Utility** (Meta may re-categorise it as Marketing; that changes the price,
    not whether it works — tell Gautam if it happens).
  - Names, lowercase with underscores, e.g. `arogya_welcome_en` and `arogya_welcome_ml`.
  - Languages: English → note whether you picked **English (US)** (`en_US`) or **English**
    (`en`); Malayalam → `ml`.
- [ ] Wait for both to show **Active / Approved**.
- [ ] Copy the approved body text **exactly**, character for character, including the
      `{{1}}` and `{{2}}`. It is used for the staff preview screen.

---

## Phase 5 — Permanent access token and app secret (~20 min)

- [ ] business.facebook.com → Settings → Users → **System users** → Add → name
      `arogya-whatsapp`, role **Admin**.
- [ ] Assign assets to it: the app (full control) and the WhatsApp account (full control).
- [ ] **Generate new token** → choose the app → expiry **Never** → permissions
      `whatsapp_business_messaging` and `whatsapp_business_management`. Copy it straight
      into Render in Phase 6. It is shown once.
- [ ] developers.facebook.com → app → App settings → Basic → **App secret** → Show.
- [ ] Note the current **Graph API version** shown in the app dashboard (format `v23.0`,
      `v24.0` …; use whatever is current, it must end in `.0`).

---

## Phase 6 — Database migration on Neon

The feature needs extra columns on the `whatsapp_logs` table. Migration file:
`backend/alembic/versions/7a8b9c0d1e2f_meta_whatsapp_welcome.py`. It only **adds nullable
columns and unique indexes**; it does not change or delete existing rows. Its parent is
`0c682ef81de1`, and it is the only head.

First check whether the live site is already affected: PR #43 code may already be deployed on
Render without these columns. Log in to the admin app and open the **Messaging** screen. If
it errors, note it for Gautam — the migration below is the fix.

- [ ] **CHECKPOINT C** — send Gautam the exact Neon project, branch and host name you are
      about to migrate, and wait for a written "yes, migrate <that target>". This is a
      standing project rule for any command against the hosted database.
- [ ] In Neon, create a **backup branch** of the production branch first (Branches → Create
      branch from current state, name `pre-meta-whatsapp-2026-xx-xx`).
- [ ] On your machine, from `backend/` with the project's virtualenv:

      ```powershell
      $env:DATABASE_URL = "<Neon connection string — paste it only in this terminal>"
      alembic current
      ```

      Expect `0c682ef81de1`. **If it shows anything else, stop and tell Gautam.**

      ```powershell
      alembic upgrade 7a8b9c0d1e2f
      alembic current
      ```

      Expect `7a8b9c0d1e2f (head)`. Then close the terminal so the URL is not left in the
      session.
- [ ] Send Gautam the output of both `alembic current` commands (no connection string in it).
- [ ] Re-open the admin **Messaging** screen and confirm it loads.

Rollback if needed: `alembic downgrade 0c682ef81de1` (drops only the new columns), or
restore from the backup branch.

---

## Phase 7 — Configure the server and connect the webhook (~30 min)

Generate the two random values on your machine:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The first is the webhook verify token, the second the recipient hash secret. Generate them
once and never change the hash secret afterwards.

- [ ] Render → backend service → Environment → add, **keeping enabled false for now**:

| Variable | Value |
|---|---|
| `META_WHATSAPP_ENABLED` | `false` |
| `META_WHATSAPP_ACCESS_TOKEN` | system-user token (Phase 5) |
| `META_WHATSAPP_PHONE_NUMBER_ID` | phone number ID (Phase 3), digits only |
| `META_WHATSAPP_GRAPH_VERSION` | e.g. `v24.0` (Phase 5) |
| `META_WHATSAPP_APP_SECRET` | app secret (Phase 5) |
| `META_WHATSAPP_VERIFY_TOKEN` | first random value above |
| `META_WHATSAPP_TEMPLATE_EN` | e.g. `arogya_welcome_en` |
| `META_WHATSAPP_TEMPLATE_ML` | e.g. `arogya_welcome_ml` |
| `META_WHATSAPP_TEMPLATE_BODY_EN` | exact approved English body |
| `META_WHATSAPP_TEMPLATE_BODY_ML` | exact approved Malayalam body |
| `META_WHATSAPP_LANGUAGE_EN` | `en_US` or `en` — must match the template |
| `META_WHATSAPP_LANGUAGE_ML` | `ml` |
| `PUBLIC_PATIENT_BASE_URL` | `https://arogya.gothoslabs.com` — origin only, no trailing path |
| `META_WHATSAPP_ENABLED_HOSPITAL_SLUGS` | comma-separated slugs from Phase 2 |
| `WHATSAPP_RECIPIENT_HASH_SECRET` | second random value above (≥32 chars) |

- [ ] Save and let Render redeploy. Wait until the service is live (free-tier Render may
      take a minute to wake up; open the API URL once in a browser first).
- [ ] developers.facebook.com → app → WhatsApp → **Configuration** → Webhook → Edit:
  - Callback URL: `https://hospital-ai-platform.onrender.com/api/v1/whatsapp/webhook`
  - Verify token: the same first random value
  - **Verify and save.** If it fails, check the token matches exactly and the service is awake.
- [ ] Webhook fields → **Subscribe** to `messages`.
- [ ] Switch the app to **Live** mode (top of the app dashboard). Apps in development mode
      do not receive real webhooks. This needs the privacy policy URL from Phase 1.

---

## Phase 8 — Controlled live test

- [ ] **CHECKPOINT D** — tell Gautam you are ready; agree which phone numbers will receive
      the test (yours and/or Gautam's only).
- [ ] Render → set `META_WHATSAPP_ENABLED=true` → wait for redeploy.
- [ ] Log in to the admin app as staff of one enabled hospital → **Messaging**.
- [ ] Send the **English** welcome to the test number. Then the **Malayalam** one.
- [ ] For each, confirm and write down:
  - [ ] It arrives from **Arogya** (verified name or the number).
  - [ ] The hospital name is right and the Malayalam text renders correctly.
  - [ ] The link opens `https://arogya.gothoslabs.com/p/<slug>` for **that** hospital and
        the assistant answers.
  - [ ] The status on the Messaging screen moves to **delivered**, then **read** after you
        open it. (If it stays on accepted/sent, the webhook is not arriving — recheck
        Phase 7.)
- [ ] Repeat with a second enabled hospital to confirm each hospital gets its own link.
- [ ] Send Gautam a short report: date/time, hospitals tested, languages, the four checks
      above for each, and any errors shown (error codes only, no phone numbers).
- [ ] **CHECKPOINT E** — Gautam decides whether staff may use it with real patients.
      Until he says yes, set `META_WHATSAPP_ENABLED=false` again after testing.

---

## If something goes wrong

| Symptom | Likely cause |
|---|---|
| Messaging screen says setup required | A variable in Phase 7 is missing or malformed: version not `vNN.0`, phone ID not digits, base URL not plain `https://host`, hash secret < 32 chars, body text missing `{{1}}`/`{{2}}`, or the hospital's slug isn't in the allowlist. |
| `hospital_not_enabled` | Add the hospital's slug to `META_WHATSAPP_ENABLED_HOSPITAL_SLUGS`. |
| `failed` / `provider_rejected` | Meta refused the send. The app deliberately doesn't store Meta's raw reply, so reproduce it from the app's WhatsApp → API Setup page or check WhatsApp Manager. Common: template name/language mismatch, payment method missing, number or display name not yet approved. |
| `failed` / `delivery_failed` | Meta accepted it but couldn't deliver: recipient not on WhatsApp, phone off for long, or Meta's per-user marketing limits. |
| Status stays `accepted` or `sent` | Webhook not subscribed to `messages`, app not in Live mode, or app secret wrong (Render logs show 403 on `/api/v1/whatsapp/webhook`). |
| Status `unknown` | Meta may or may not have sent it. **Do not send again to that number.** Check in WhatsApp Manager first, then tell Gautam. |
| Webhook verify fails in Meta | Verify token mismatch, or Render asleep / not redeployed yet. |
| Patient page has a CORS error | `ALLOWED_ORIGINS` on Render is missing the new domain. |

**Emergency stop:** set `META_WHATSAPP_ENABLED=false` on Render. New sends stop; delivery
updates for messages already sent keep working.

## When you are done

- [ ] Gautam has: WhatsApp Business Account ID, phone number ID, template names, the
      two-step PIN, and the test report.
- [ ] Every secret is in Render only (and Gautam's password manager if he wants it).
- [ ] Gautam decides which of your access grants to keep or remove.
- [ ] The project status file (`docs/STATUS.md`) is updated by Gautam's agent workflow, not
      by hand.

---

## Appendix — prompt for your AI assistant

Paste this as the first message to whichever AI helps you (Claude, ChatGPT, Codex …). If it
can read the repository, it reads this guide itself; otherwise paste this whole file after
the prompt.

```text
You are helping me activate WhatsApp welcome messages for Arogya, an AI hospital assistant
made by Gothos Labs. The code is already built and merged. My job is account setup, server
configuration, one database migration and a controlled live test. I do the clicking and
typing; you guide me.

Source of truth: docs/WHATSAPP_ACTIVATION_HANDOVER.md in the GitHub repo
Gotham28/hospital-ai-platform (engineering detail: docs/WHATSAPP_SETUP.md). If you can read
the repo, read both before answering. If you can't, ask me to paste the handover guide.
Follow its phases in order.

This repo has AGENTS.md rules written for coding tasks. This is not a coding task: no
CURRENT_TASK.md, no dispatching, no commits, no code edits. Its safety rules still apply,
especially: no command against the hosted (Neon) database without the owner's written OK.

How to help me:
- First ask which phase and step I'm on. Don't assume anything was done.
- One small step at a time. Say exactly where to click or what to type, then wait for me
  to confirm or send a screenshot before the next step.
- Meta, Render, Vercel and Neon screens change. If my screen doesn't match the guide, work
  from my screenshot and say so. Don't invent menu names.
- Stop at every CHECKPOINT (A to E) in the guide and tell me to get the owner's written OK
  before going on. Don't help me skip one.
- If an error shows up, check the guide's "If something goes wrong" table first. If a
  message status is "unknown", tell me not to send again to that number.
- At the end of each phase, write a 3-line update I can send the owner: what was done, IDs
  recorded (never secrets), anything blocked.

Never:
- Ask me to paste or show a secret: access token, app secret, webhook verify token,
  recipient hash secret, two-step PIN, or the Neon connection string. Remind me to hide them
  in screenshots. You only need to know a value is set, not what it is.
- Write or change code, the migration file or any repo file. If something seems to need a
  code change, stop and tell me to report it to the owner.
- Suggest any database command other than the exact alembic steps in Phase 6, and only
  after Checkpoint C.
- Suggest testing with real patient numbers, or turning META_WHATSAPP_ENABLED on outside
  Phase 8.
- Present message wording or privacy-policy text as final. Drafts are fine if clearly
  labelled for the owner to approve.
- Suggest logging in with the owner's personal Facebook account, or entering payment card
  details myself.
```
