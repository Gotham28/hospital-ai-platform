# Guard follow-up execution brief for another AI

**Repository:** `D:\Hospital\hospital-ai-platform`  
**Date:** 2026-10-27  
**Goal:** Correct the remaining English and Malayalam research-guard failure modes, then run a reproducible full evaluation. The developer has deferred acting on the completed review and wants future review later. Return code, evidence, and `HANDOFF.md`; do not treat this brief as an accepted review or close-out.

## Read this first

1. Read the developer's global `AGENTS.md`, `.agents/AGENTS.md`, `.agents/CURRENT_TASK.md`, this brief, and the relevant sections of `backend/research/README.md`. The project requires one feature per task/diff, an approved `CURRENT_TASK.md`, the executor named there, and a separate review/close-out stage. Execute the work packages below as **separately scoped tasks**, even though the developer wants the whole program completed. Do not overwrite the active task without their explicit approval.
2. The current English action-policy task has a final four-lens **accept-as-is recommendation**, but developer acceptance is pending. The developer explicitly said review will happen later. Preserve that state; do not edit `docs/STATUS.md`, commit, push, open a PR, or claim the task was accepted. Existing unrelated dirty files, including the `backend/google_credentials.json` deletion, must be preserved.
3. The guard is isolated research code. Do not import `backend/research` into `backend/app`, change production behavior, alter model weights, or change the previous benchmark outputs. Do not run `backend.research.run_guard_nli_test.main()` because it rewrites thresholds.

## Current measured baseline

- Active English action policy is `BASELINE`; no tested threshold-only action candidate met the frozen tradeoff. V3 calibration ran **720 development** and **360 reserved validation** RAGTruth-train answers with complete command logs and producer identities. Development baseline falsely altered **395/399** no-span answers and fully intercepted **259/321** annotated-error answers. Validation: **205/207** and **130/153**. Source-group split and all candidate results are in `backend/research/results/guard-action-policy-2026-10-27/`.
- The prior full CUDA public benchmark completed **22,740/22,740** conditions with zero failures. English XNLI guard falsely altered **510/1,670** supported answers; Malayalam **1,203/1,670**. RAGTruth falsely altered **1,733/1,757** no-span answers; annotated-error interception was **814/943**, with **4.34%** redacted-character precision. See `backend/research/results/guard-external-2026-10-26/full-cuda/metrics.json` and `backend/research/notes/guard_external_performance_2026-10-26.md`.
- Long inputs are common: **4,342/6,427** development and **1,965/3,232** validation claim/evidence pairs exceeded the model's 512-token limit. Truncation cannot be assumed to explain all false flags: the earlier analysis also found **672/693** no-truncation RAGTruth no-span answers falsely flagged. The original RAGTruth context was passed intact, so evidence selection and NLI calibration need direct tests.
- Existing diagnosis found numeric/time parser errors (`11:0` versus `11:00`, colon overmatching), and sentence splitting at `Batman v.`. Numeric-only removal cleared **zero whole-answer false alterations** with other verdicts frozen. Malayalam pivot translation versus native scoring has not been isolated in a controlled full ablation.

The public XNLI/IndicXNLI and RAGTruth **test** labels have already been inspected. They are exploratory comparison sets, never tuning/selection sets. Existing RAGTruth **train** groups used in v3 calibration are also no longer a fresh final holdout.

## Work packages — scope each independently

### 1. Establish claim-level error labels and a genuinely untouched holdout

Define an evaluation unit for each extracted claim: source evidence, entailment/contradiction/unknown gold label, exact error spans, language, task, source group, and annotation confidence. Audit no-span RAGTruth answers for incomplete annotation rather than assuming every one is fully correct. Create source-grouped development and reserved validation data without leaking source groups or answers across partitions. Locate and license-check an independent final dataset or arrange blind annotation **before** selecting models/thresholds. Freeze IDs, hashes, sampling seed, annotation policy, metrics and decision rule in a manifest. Report disagreements and uncertain labels; do not invent gold labels from the guard's own predictions.

**Gate:** reproducible manifest; independent label checks; no overlap or test-label tuning; explicit denominators and an untouched final holdout.

### 2. Fix long-context evidence selection

Measure where relevant evidence is lost or diluted. Compare intact context with deterministic passage/sentence windows, claim-to-evidence retrieval and top-k evidence aggregation on development groups. Keep source offsets and an audit trail of which original passage supported each verdict. Do not silently discard contradictory evidence. Measure truncation, false alterations, error interception, character precision/recall, and latency. A shorter input alone is not success; it must improve labeled outcomes, including the no-truncation subgroup.

**Gate:** predeclared development winner, reserved-group confirmation, source-cluster confidence intervals, bounded GPU memory/latency, and no regression hidden by task subgroup averages.

### 3. Recalibrate detection and the action decision

Only after claim labels and evidence selection are sound, compare the current pinned mDeBERTa model with justified candidate models or calibration methods. Cache per-claim model scores once, then replay threshold/action policies; do not rerun the GPU for every threshold. Preserve distinct fields for detection verdict, action/redaction and exact-rule provenance. Predeclare a false-alteration versus missed-error rule before seeing validation. The prior minimum rule was at least **20 percentage points** fewer false alterations while retaining at least **50%** of baseline complete interception; choose and record a stronger paper-appropriate target if the labeled data supports it. If no candidate passes, keep baseline and report a negative result.

**Gate:** held-out improvement with uncertainty and denominators; no unexplained recall collapse; stable source/model/data identity and resumable logs. Do not change the frozen old benchmark's identity to make new code run; create a versioned candidate run.

### 4. Diagnose and repair Malayalam separately

Use paired English/Malayalam cases with the same source group and claim meaning. Compare native Malayalam NLI, pivot translation, and any justified alternative under the same evidence and labels. Log translation and score provenance without patient text or security logs. Check translation mistakes, claim segmentation, exact numeric overrides, and whether English evidence paired with Malayalam answers creates a language mismatch. Preserve English gains while changing Malayalam.

**Gate:** Malayalam false alterations and missed errors improve on reserved paired groups, with paired source-group confidence intervals and explicit translation/latency cost. Do not infer the cause from the earlier 12 purposively selected traces alone.

### 5. Repair parsers in separate focused diffs

First fix numeric/time/price normalization and type matching with adversarial synthetic tests (`11:0`/`11:00`, colon punctuation, Malayalam digits, units, prices). Then fix English and Malayalam claim segmentation with abbreviation and multi-clause tests, including `Batman v.`. Re-run the labeled evaluation after each change; show whole-answer effects, not only corrected individual claims. Keep these as separate tasks from model and retrieval changes.

**Gate:** each parser fix has adversarial regressions, a measured downstream effect, and no loss of supported claims. A local parser test pass is not evidence of overall guard improvement.

### 6. Run the combined final evaluation and paper-ready report

Freeze code, model revisions, thresholds/action policy, data hashes, source-group memberships and metrics **before** final evaluation. Run a small fixed preflight first, then one complete GPU run with a versioned output directory; no candidate tuning after reading final labels. Include English and Malayalam detection, false alterations, complete error interception, residual errors, redacted-character precision/recall, task/quality subgroups, truncation, failure counts, latency p50/p95, peak GPU memory and source-group bootstrap intervals. Compare to the existing 22,740-condition baseline, but identify the prior inspected public tests as exploratory; use the untouched holdout for the primary improvement claim. Write a plain-language summary and exact commands/full raw outputs in `HANDOFF.md`.

**Gate:** every selected case has one outcome or explicit error; no mixed identities or duplicate IDs; zero silent CPU fallback; limitations and negative results remain visible. Stop for the developer's deferred independent review and STATUS/close-out decisions.

## Efficient execution and handoff

- Use the existing research environment: `D:\Hospital\hospital-ai-platform\backend\research\.venv\Scripts\python.exe`. The completed benchmark used the RTX 3050 Laptop GPU (4 GB), float32, TF32 off, and four CPU threads. Check CUDA availability and memory before a full run; record device, precision and versions. Do not silently switch to CPU.
- For every candidate, run unit/adversarial tests and a bounded preflight before a long evaluation. Save exact command, complete stdout/stderr, exit code, input/source/model hashes and completion counts. Never backfill or invent a missing historical terminal transcript.
- Reuse cached scores for policy sweeps; run the expensive assembled guard only on frozen finalists. Keep train/development/validation/final sets distinct. Preserve old and v2/v3 results; use new versioned directories for new experiments.
- Use inexpensive available models for file surveys, test writing and log formatting. Reserve stronger reasoning for causal diagnosis, model/evaluation design and disputed review findings. The task file still decides the actual executor and xhigh review assurance; do not claim an unavailable model setting changed.
- Return an implementation handoff after each scoped task: changed files, rationale, full raw verification output, failures/limits, baseline deltas and the next task. Formal review is deferred by the developer; do not mark any task accepted or close it without that later decision.
