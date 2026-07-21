# AROGYA — Master Development & Research Plan
### Product Upgrade + "Multi-Tenant Agentic Architecture for Low-Resource Languages" Paper

This document merges three earlier planning threads (Product Improvement prompt, Research
Instrumentation prompt, and paper requirements from *Initial_Submission_Final_updated.docx*)
into one execution plan, corrected against your actual submitted paper objectives and your
real codebase (`repomix-output.xml`).

---

## 0. Core Philosophy (locked in)

- **One system, two zones.**
  - `backend/app/...` = production. Permanent improvements go here. Never broken.
  - `backend/research/` = paper instrumentation. Fully isolated — never imported by
    production code, runnable standalone (`python -m backend.research.xxx`), gitignored
    `results/` folder for output.
- **After the paper is published**, deleting `backend/research/` must leave the product
  100% functional — no shared imports, no production code path depends on a research file
  or a research-only config key.
- **Research tests the upgraded system.** Phase 2 benchmarks run against the Phase-1
  version of AROGYA (Sarvam translation, personalisation, hardened security), not the
  original, so your paper's numbers reflect the system you actually shipped.
- **New DB migrations are reviewed by you before being applied** — this includes the
  `add_research_embeddings` migration and any patient-context/security-log tables.

---

## 1. What Changed From the Original Three Prompts (read this first)

Your actual paper (as submitted) is **more specific and in some places different** from
the earlier "research prompt." Corrections locked in after review:

| Topic | Earlier prompt said | Paper actually requires | Decision |
|---|---|---|---|
| Translation baseline | Sarvam vs Google | mBERT / XLM-R vs professional reference (BLEU/chrF) | **Both**: product uses Sarvam (with Google fallback); paper *also* benchmarks mBERT/XLM-R as academic baselines in `backend/research/translation_eval.py` |
| Retrieval comparison | E5 vs sentence-transformers vs OpenAI | Not explicitly required by paper, but strengthens the RAG section | **Keep** — still valuable supporting evidence, done in Phase 2 |
| LLM comparison | GPT-4o-mini vs Llama 3 vs Mistral (via Groq) | Not explicitly required, but strengthens results | **Keep**, gated on you obtaining a Groq key (see §5) |
| Dialogue dataset | Not mentioned | Paper requires a **synthetic Malayalam scheduling dialogue dataset**, publicly released | **Upgraded to real data** — see §6, this is now a consent-gated real-query pipeline, not synthetic |
| Tenant isolation | Assumed correct, not formally tested | Paper requires isolation proof across ≥2 tenants | **New script added**: `tenant_isolation_test.py` |
| Load testing | Not mentioned | Paper requires latency under concurrent load | **New script added**: `load_test.py` |
| Security eval | Confusion matrix vs hand-built attack set | Same, informed by OWASP LLM Top 10 | Unchanged |

---

## 2. Phase 1 — Product Improvements (Weeks 1–4)

All changes land directly in `backend/app/...`. No behavior regressions. Order matters —
each step below unlocks a cleaner version of the next.

### 1.1 Patient Personalisation (session-aware context)
- New `services/patient_context.py`. Stored in Redis, same key pattern as booking session
  (`booking:{hospital_id}:{session_token}`).
- Track: doctor/department mentioned, language preference, info already given this session.
- Inject a **"Patient context this session:"** block into `build_context()` only when data exists.
- Success metric: task completion rate (turns/time to booking) — logged, not just eyeballed,
  since you'll want this number for the paper's dialogue-agent evaluation too.

### 1.2 Extract services out of `ai.py`
- Currently one ~800-line file mixing RAG, translation, booking, security, intent logic.
- Split into: `services/rag.py`, `services/patient_context.py`, `services/translation.py`,
  `services/booking.py`, `services/security.py`.
- Pure refactor — no signature changes without flagging it first.

### 1.3 Upgrade cross-lingual pipeline (production)
- Primary: **Sarvam AI** (`SARVAM_API_KEY`, already in `config.py`) for ml↔en.
- Post-process Malayalam output: enforce "ഡോക്ടർ [Name]" prefix, formal pronouns
  (e.g. "അദ്ദേഹം"), consistent doctor-name normalization.
- Fallback to Google Translate with a circuit breaker if Sarvam fails.
- Cache common translations in Redis.

### 1.4 Security hardening
- Extend `_INJECTION_PATTERNS` with Malayalam equivalents, informed by OWASP LLM Top 10
  (this doubles as the seed set for the paper's adversarial test suite in Phase 2).
- New `SecurityLog` table: timestamp, hospital_id, matched pattern, **hash** of raw text
  (never store raw patient text in a security log).
- Consistent, friendly, language-correct rejection message.
- Per-hospital + per-IP rate limiting.

### 1.5 Multi-tenant isolation hardening
- Confirm doctor embedding search always filters by `hospital_id` — no fallthrough path.
- Add a runtime assertion in context-building that blocks cross-tenant leakage.
- Confirm `hospital.system_prompt` is actually wired into `build_context()`.
- This is also prep work for the Phase 2 tenant isolation *test* (§4.6) — the assertion
  you add here becomes the thing that test tries to break.

**End of Phase 1 checkpoint:** demo the personalised, Sarvam-translated, hardened system
end-to-end before touching any research code.

---

### 1.6 IRIS Rheumatology Clinic — Requested Features (priority insert, IRIS-specific)

The clinic administration requested five additions after a direct meeting. **These are
scoped entirely to `hospital_id` (IRIS) via admin-configurable fields — none of this
changes AROGYA's base model, prompt logic, or behavior for any other tenant.** This work
is inserted ahead of §1.2 (service extraction) since the clinic marked it priority; §1.1
(Patient Personalisation) is already complete and unaffected.

**Scope note:** the clinic's original ask also included per-patient handwritten-record
upload (OP tickets, nurse inspection notes, doctor verdicts) as chat context. **This has
been dropped from the current round** — the clinic confirmed new-patient flows only, no
patient-record ingestion yet. It remains a documented future item, not built.

**Feature 1 — Welcome message**
- Config-only. Extend `hospital.system_prompt` (or a dedicated `welcome_message` field)
  in the admin "Train AI" page with a brief description of the clinic's procedure.
- Fires on a patient's first message in a session.

**Feature 2 — Waiting-time disclaimer**
- Config-only. New field `hospital.post_booking_disclaimer` (text), appended to the
  booking-confirmation message.
- Draft wording (pending clinic sign-off, IRIS's stated duration is 2 hours):
  > "Please note: the full consultation process — including any tests or examinations —
  > may take approximately 2 hours. We recommend planning your visit with this in mind."

**Feature 3 — Outsourced lab test flag**
- Schema: add `is_outsourced BOOLEAN DEFAULT FALSE` and `outsourced_note TEXT NULL` to
  the `LabTest` table.
- Admin UI: toggle + free-text note per lab test row, staff-editable per clinic.
- Behavior: when the AI mentions/recommends a flagged test, it appends `outsourced_note`.
- Draft wording (pending clinic sign-off):
  > "This test is processed by an external laboratory. While we work with trusted
  > partners, turnaround time and quality standards for this specific test may vary and
  > are not directly controlled by Iris Rheumatology Clinic."

**Feature 4 — Rheumatology-relevance gate before booking**
- New config field `hospital.relevance_criteria` (free text, admin-editable) — keeps this
  feature reusable for any specialty clinic, not hardcoded to rheumatology.
- New DB column `Appointment.relevance_reason` (text), surfaced as a new column in the
  admin appointments table.
- Flow (confirmed with clinic, criteria still partial):
  1. Ask: "Has a doctor referred you to us?" → if yes, treat as relevant, proceed.
  2. If no: ask which doctors/specialists the patient has consulted for this before →
     match against `relevance_criteria`.
  3. If still ambiguous: ask the patient to briefly describe their main symptom, log the
     reasoning into `relevance_reason`, and route to a **staff review flag** rather than
     auto-booking or auto-declining — safest default until the clinic finalizes full
     criteria.
- **Blocked on clinic:** remaining relevance criteria beyond referral/prior-doctor checks.
  Retrofitting these later is a config edit, not a code change.

**Feature 5 — Patient handwritten-record context** *(deferred, documented for later)*
- Not built this round. If revisited: recommended approach is a hybrid pipeline — extract
  text once via a vision-LLM at upload time, require staff review/approval before the
  extracted text is usable by the patient-facing AI, and store the reviewed text (not
  re-run extraction per query). Needs a resolved patient-identity-verification method
  (name alone is insufficient) before any build starts.

**Time estimate for Features 1–4:** ~9 days total (was ~3.5 weeks including Feature 5;
dropping Feature 5 significantly shortens this).

---

## 3. Phase 2 — Research Instrumentation (Weeks 5–12)

Everything below lives in `backend/research/`.

```
backend/research/
├── __init__.py
├── test_queries.py
├── retrieval_benchmark.py
├── llm_benchmark.py
├── translation_eval.py
├── bias_analysis.py
├── security_eval.py
├── tenant_isolation_test.py
├── load_test.py
├── real_query_pipeline/        # consent + PII scrubbing (see §6)
└── results/                    # gitignored
```

### 3.1 `test_queries.py` — foundation, build first
- 50 query dicts: `id`, `query_en`, `query_ml`, `reference_answer`, `category`,
  `complexity`, `query_type`, `hospital_id`.
- **You write reference answers for queries 1–15** as the style/tone guide (medically
  accurate, matches how AROGYA should actually respond). **I generate 16–50** matching that
  style, you review before we lock the file.

### 3.2 `retrieval_benchmark.py`
- Compare `text-embedding-3-small` (current) vs `intfloat/multilingual-e5-base` vs
  `paraphrase-multilingual-mpnet-base-v2`.
- New Alembic migration `add_research_embeddings`: adds `embedding_e5 Vector(768)` and
  `embedding_st Vector(768)` to `KnowledgeBase`. **You review this migration before it's
  applied to any real database**, including a staging/copy DB, never the live hospital DB.
- RAGAs metrics (faithfulness, answer_relevance, context_recall), CSV output, English vs
  Malayalam breakdown.

### 3.3 `llm_benchmark.py`
- GPT-4o-mini (current) vs Llama 3 70B vs Mistral 8x7B, both via Groq.
- **Blocked until you have a Groq key** — see §5.
- RAGAs faithfulness/relevance + ROUGE-L, broken out by language.

### 3.4 `translation_eval.py`
- Two comparisons, both against the same 30 Malayalam↔English professionally-translated
  reference pairs:
  - **Production track**: Sarvam (primary) vs Google (fallback) — proves the product
    upgrade actually improved translation quality.
  - **Academic baseline track**: mBERT vs XLM-R — matches the paper's stated objective 1
    exactly, needed regardless of what the product uses internally.
- Score both tracks with `sacrebleu` (BLEU, chrF).

### 3.5 `bias_analysis.py`
- Probe sets: urban vs rural-style queries, expensive vs basic-care queries, simple vs
  complex multi-turn.
- RAGAs scores per category + `scipy` significance testing.

### 3.6 `tenant_isolation_test.py` *(new)*
- Seed ≥2 test hospital_ids with deliberately overlapping data (e.g. both have a doctor
  named "Dr. Priya" in different departments).
- Fire identical queries at each tenant; assert retrieved chunks and final answers for
  Tenant A never contain Tenant B's content, and vice versa.
- Output: pass/fail isolation report — this is the paper's "≥2 concurrent tenants, zero
  cross-tenant leakage" evidence.

### 3.7 `load_test.py` *(new)*
- Async load generator (e.g. `asyncio` + `httpx`, or `locust`) hitting the chat endpoint
  at increasing concurrency (10 / 50 / 100 simultaneous sessions — set the ceiling to
  something realistic for a single hospital's expected traffic, not arbitrary thousands).
- Measure p50/p95/p99 latency, error rate, timeout rate.
- **Run only against a staging/local instance — never the live hospital deployment.**
- Output: latency-vs-concurrency chart for the paper.

### 3.8 `security_eval.py`
- 60 inputs: 30 genuine (true negatives), 30 adversarial (true positives), English +
  Malayalam variants, drawing on OWASP LLM Top 10 patterns.
- Run through `detect_prompt_injection()`. Output: confusion matrix, precision/recall/F1.

### Dependencies to add to `requirements.txt`
```
ragas
sacrebleu
groq
scipy
sentence-transformers
datasets
transformers   # for mBERT / XLM-R baseline
httpx          # or locust, for load_test.py
```

---

## 4. What Stays Manual / Needs Your Sign-off

- Applying `add_research_embeddings` migration to any database.
- Running `load_test.py` against anything other than a local/staging instance.
- Finalizing the query 16–50 reference answers before they're used to score anything.
- Anything touching real patient data (§6) — consent copy, retention period, what counts
  as PII in a Malayalam medical context, and whether an institutional ethics/IRB review is
  needed before real queries are logged or before any subset is prepared for public release.

---

## 5. Getting a Groq API Key (blocks §3.3)

1. Go to **console.groq.com** and sign up (Google/GitHub/email).
2. Once in the console, go to **API Keys** in the left sidebar → **Create API Key**.
3. Name it (e.g. `iris-research`), copy the key immediately — it's shown once.
4. Add it to `backend/app/core/config.py` as `GROQ_API_KEY`, same pattern as
   `SARVAM_API_KEY`. Never commit it — confirm it's in `.gitignore`'d env config.
5. Groq's free tier has generous rate limits for Llama 3 / Mistral, but 50 queries × 2
   models × multiple runs (for statistical stability) can still add up — check current
   rate limits in the console before running the full benchmark, and run a 5-query smoke
   test first.

Tell me once you have the key and I'll wire it into `llm_benchmark.py`.

---

## 6. Real Patient Query Pipeline (replaces "synthetic dataset")

You opted to build this for real, which is a stronger paper contribution — but it's a
different engineering task than "generate 50 fake queries," and it's the one place in this
plan with genuine legal/ethical exposure since this is a live hospital serving real
patients. Building this responsibly means:

1. **Consent first, logging second.** No query gets captured for research/dataset purposes
   unless the patient has affirmatively opted in — a passive "by using this you agree"
   banner is not sufficient for a published dataset. Needs an explicit opt-in step in the
   chat flow, separate from normal usage.
2. **Institutional sign-off.** Before any real patient text is stored for research purposes
   or prepared for public release, check with the hospital administration and your
   supervisor (Jisha RC) on whether this needs formal ethics committee / IRB approval —
   this is standard for any healthcare human-subjects data collection in an academic paper,
   and reviewers will likely ask about it regardless.
3. **PII scrubbing pipeline** (`backend/research/real_query_pipeline/`): strip patient
   names, phone numbers, ID numbers, and any other identifiers from captured queries before
   they're used for scoring or considered for the public dataset. This needs to run on both
   the Malayalam and English text.
4. **Two-tier storage:**
   - **Internal research set** (opt-in, consented, PII-scrubbed) — used for your own
     benchmarking in Phase 2, kept private to the project.
   - **Public release subset** — a further-reviewed, smaller, hospital/administration
     approved slice, only if institutional sign-off clears it. If it doesn't clear in time
     for your deadline, fall back to a synthetic dataset built from the same categories for
     the public release, while still using real (internal-only) data for your own benchmarks.
5. This pipeline is scoped for **Week 9–11** (after core research scripts exist) so it
   doesn't block everything else, and so you have time to get institutional sign-off in
   parallel.

I have not built any of this yet — it needs your confirmation on consent flow wording and
institutional approval status before real patient text touches any storage.

---

## 7. Weekly Action Plan — Mapped to 23AID498 Phase 1 Milestones

Your college schedule (Internal Component, 70 marks) sets fixed checkpoints between now
(4 July 2026) and 23 Oct 2026. The plan below is built from those exact dates, with a
**weekly presentation deliverable** in every row since you report progress weekly
regardless of which milestone is next. Phase 1 (product) and early Phase 2 (research) are
interleaved so "Existing System and Problem Formulation" and "Baseline comparisons" (20 Jul
milestone) are backed by real numbers, not just descriptions.

| Week | Dates | Focus | Weekly presentation should show | College milestone |
|---|---|---|---|---|
| 1 | 4–11 Jul | Patient Personalisation (§1.1) | Redis-backed session context live; demo of "doesn't repeat itself" | — |
| 2 | 12–20 Jul | **Superseded — see §7a.** IRIS clinic-requested features (Features 1–4) take full priority this week; service extraction and journal survey do not happen this week. | Clinic feature progress (welcome message, disclaimers, lab-test flag, relevance-gate mechanism) | Feeds into 20 Jul — milestone unaffected, doesn't require code refactor |
| **—** | **20 Jul** | **Existing System & Problem Formulation (10 marks)** | Zeroth presentation: architecture, 5+ journal papers/student, research gap, problem statement, **baseline comparisons** (early Sarvam-vs-Google samples as first baseline), expected outcome, viva | Direct deliverable |
| 3 | 21–26 Jul | Service extraction (§1.2) — `ai.py` → `services/`, no behavior change | `ai.py` split into `services/`; tests passing | — |
| 3b | 27–29 Jul | **Compressed**: Sarvam translation upgrade (§1.3) + System Design draft, now squeezed into ~3 days ahead of 30 Jul | Before/after Malayalam output; system design diagrams drafted — **flagging risk below** | Feeds into 30 Jul |
| **—** | **30 Jul** | **System Design (5 marks, guide-assessed)** | Architecture diagram (production vs research split, §0), data flow, DB schema incl. planned `add_research_embeddings` migration | Direct deliverable |
| 4 | 31 Jul–7 Aug | Security hardening + isolation check (§1.4, §1.5) | `SecurityLog` table live, Malayalam injection patterns added, isolation assertion in place | — |
| 5 | 8–11 Aug | `test_queries.py` (your 1–15 + my 16–50); freeze Methodology chapter | 50-query file drafted; Methodology ready for Mid Review | Feeds into Mid Review |
| **—** | **12–21 Aug** | **Mid Review (25 marks)** | Methodology, Project Progress (Phase 1 complete + research scaffold), time plan for Phase 2, viva | Direct deliverable — biggest checkpoint so far |
| 6 | 22–29 Aug | Run `retrieval_benchmark.py` | CSV comparing 3 embedding models, English vs Malayalam | Project diary entry |
| 7 | 30 Aug–5 Sep | Groq key (§5) + `llm_benchmark.py` | GPT-4o-mini vs Llama 3 vs Mistral comparison table | Project diary entry |
| 8 | 6–12 Sep | `translation_eval.py` — both tracks | Sarvam-vs-Google AND mBERT-vs-XLM-R, BLEU/chrF tables | Project diary entry |
| 9 | 13–19 Sep | `bias_analysis.py`; start real-query consent-flow draft | Bias report with significance tests; consent UI draft for hospital review | Project diary entry |
| 10 | 20–27 Sep | `tenant_isolation_test.py` + `load_test.py`; compile diary | Isolation pass/fail report; latency-vs-concurrency chart (staging only) | Feeds into 28 Sep |
| **—** | **28 Sep** | **Code/Progress Review (15 marks, guide-assessed)** | Weekly project diary submitted, working demo covering Phase 1 + research through Week 10 | Direct deliverable |
| 11 | 29 Sep–5 Oct | `security_eval.py` + real-query PII scrubbing pipeline | Confusion matrix report; scrubbing pipeline tested on sample data | Project diary entry |
| 12 | 6–12 Oct | Institutional sign-off checkpoint; consolidate all CSVs | Go/no-go on public real-data release vs synthetic fallback | Project diary entry |
| 13 | 13–19 Oct | Write Phase 1 paper — Results & Evaluation sections | Draft sections using Weeks 5–12 outputs | Feeds into 23 Oct |
| **—** | **23 Oct** | **Phase 1 Paper Publication — soft copy (10 marks, guide-assessed)** | Full report submitted | Direct deliverable |

**Why Weeks 1–2 span 16 days instead of 14:** the first milestone lands 16 days from today;
every week after that runs on a clean 7-day cadence.

**External Component (30 marks)** is review-panel-assessed and not something this plan
controls directly — but the structure above means you always have a working demo and real
numbers ready if the panel calls a review outside the fixed dates.

---

## 7a. IRIS Clinic-Requested Work — Priority Insert (kept separate from §7)

Inserted ahead of the original Week 2 (service extraction), starting 14 July. This does
**not** replace or renumber the Section 7 table above — treat this as a priority detour
that Section 7's "Week 2" onward now follows, shifted by ~9 days in practice.

| Days | Work | Depends on |
|---|---|---|
| 14–15 Jul | Feature 1 (welcome message) + Feature 2 (waiting-time disclaimer) | Nothing — config only |
| 16–18 Jul | Feature 3 (outsourced lab test flag + admin toggle) | Nothing — schema + admin UI |
| 19–20 Jul | Feature 4 (relevance-gate mechanism: referral → prior-doctor → staff-review fallback; `relevance_reason` column + admin view) | Partial — remaining criteria still pending from clinic |
| 21–26 Jul | Resume Section 7: service extraction (`ai.py` → `services/`); journal survey (separate teammate) continues in parallel, unaffected by this detour | — |
| 27–29 Jul | **Compressed** Sarvam translation upgrade + System Design draft — see risk flag below | — |

**Risk flag:** squeezing Sarvam translation + System Design into 27–29 Jul (3 days,
down from the original 9) ahead of the 30 Jul milestone is tight. If Feature 4's
relevance-gate work spills past 20 Jul, or service extraction surfaces unexpected
issues, System Design is the piece most likely to arrive as a rougher draft. Worth
flagging to your mentor ahead of time rather than surprising them on the 30th.

Feature 5 (patient handwritten-record context) remains **not scheduled** — see §1.6.

### 7b. Sequencing Update (as of 14 Jul)

Confirmed change to the above: **ai.py extraction (§1.2) is pushed to the week after the
20 Jul milestone, and runs alone that week** — Sarvam translation upgrade (§1.3) and the
System Design draft are pushed out further as a result.

| Days | Work |
|---|---|
| 14–20 Jul | IRIS clinic updates only (Features 1–4, §1.6) — no other Phase 1 product work this week |
| 20 Jul | **Milestone: Existing System & Problem Formulation** — unaffected, doesn't require code refactor |
| 21–27 Jul | `ai.py` → `services/` extraction only (§1.2) — Sarvam and System Design explicitly **not** worked on this week |
| 28–30 Jul | Sarvam translation upgrade (§1.3) starts; System Design deliverable drafted using the **already-existing target architecture diagram** and DB schema plan — the milestone does not require Sarvam to be fully implemented, only designed |
| 30 Jul | **Milestone: System Design** — achievable even with Sarvam mid-implementation, since the diagram/schema exist independently of the code |
| 31 Jul onward | Sarvam upgrade continues to completion, then Security hardening + isolation (§1.4, §1.5) — compressed by ~1 week versus the original §7 table; Mid Review (12–21 Aug) prep should be watched for tightness |

**Net effect:** the original §7 table's Weeks 2–4 are compressed into roughly Weeks 2–4.5,
about a 1-week slip carried forward from here. Journal survey (separate teammate) is
unaffected throughout.

---

## 8. Still Open

- Groq API key (blocking Week 7) — you're getting one, ping me when ready.
- Institutional/ethics approval status for real patient data — needs a conversation with
  Jisha RC / hospital administration, not something I can resolve for you.
- Final confirmation on the consent-flow wording for real-query capture, before any code
  for it is written.
- IRIS clinic sign-off on the draft waiting-time and outsourced-lab-test disclaimer
  wording (§1.6, Features 2 and 3).
- Remaining rheumatology-relevance criteria beyond referral/prior-doctor checks (§1.6,
  Feature 4) — clinic has not fully specified these yet.
- Patient identity-verification method (name alone vs. phone/DOB/patient-ID) — required
  before Feature 5 (deferred handwritten-record context) can be scheduled at all.
