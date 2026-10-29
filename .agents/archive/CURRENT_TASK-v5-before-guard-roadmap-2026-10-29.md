# Current Task

## Feature
- Complete the Work Package 5 v5 parser evaluation evidence and handoff from existing cached scores, with GPT-6.1 reasoning and Antigravity mechanical edits.

## Plan reference
- backend/research/notes/guard_remaining_work_for_ai_2026-10-27.md: Work Package 5, then separate Work Packages 1, 2, 3, 4, and 6.
- docs/MASTER_PLAN.md section 3: isolated research and English/Malayalam metric conventions.
- docs/STATUS.md last updated 2026-09-22; research execution is explicitly authorized by the developer despite its stale description. Do not edit it.
- Re-scopes the same unfinished v5 task. Developer requested full remaining accuracy work on 2026-10-28, using Antigravity for mechanical work and GPT-6.1 for reasoning. This task finishes the current evidence package only; later packages require their own scopes.

## MASTER_PLAN.md update
- None. Existing research scope; no edits to MASTER_PLAN.md.

## Files/areas in scope
- HANDOFF.md: preserve all existing content and append the complete v5 report, exact commands, full raw outputs, exit statuses, identities, baseline comparison, limitations, and the incidental policy-sweep deviation.
- .agents/LOOP_HANDOFF.md: complete the interrupted evidence block and record the developer's decision to finish the evaluation using baseline results from the existing cached v5 scores. This is a descriptive halt record, not permission to edit governance files.
- backend/research/results/guard-parser-v5-2026-10-28/baseline-only-report.json: new report derived solely from the existing baseline-policy evaluation and cached v4/v5 traces.
- backend/research/results/guard-parser-v5-2026-10-28/completion-verification.json: new evidence checking current identities, selected/completed IDs, source groups, metadata, report contents, and preservation hashes.
- backend/research/results/guard-parser-v5-2026-10-28/completion-verification.log: exact final verification stdout/stderr and exit code.

## Explicitly out of scope
- Implementation of remaining Work Packages 1, 2, 3, 4, and 6 in this task; each is independently scoped afterward.
- Editing producer source, parser source, thresholds, model weights, or existing tests; this would invalidate current producer identity.
- Additional policy sweeps, threshold selection, model selection, or promotion. The incidental development-selection.json is retained only as evidence of the prior scope deviation.
- New GPU inference unless existing evidence is incomplete or invalid; halt rather than silently rerun or rebind an identity.
- Reserved validation, final holdout, inspected public test labels for tuning, production code, databases, credentials, dependencies, or live services.
- Formal review, acceptance, commits, pushes, PRs, close-out, STATUS.md edits, MASTER_PLAN.md edits, and repomix generation.

## Do NOT touch
- backend/app/, frontend/, .env, databases, Redis, credentials, and the pre-existing deletion of backend/google_credentials.json.
- All existing original/v2/v3/v4 results, including guard-action-policy-2026-10-27/, guard-external-2026-10-26/, and guard-performance-2026-10-26/.
- All existing v5 raw identities, traces, metrics, selection files, logs, hash captures, audits, comparison files, and verification files. Read and cite them; do not rewrite, move, delete, or rebind them.
- All unrelated dirty/untracked work, governance/rule files, .agents/CURRENT_TASK.md, .agents/DECISION.md, hooks, and permission settings during execution.
- Patient/private text. Never run backend.research.run_guard_nli_test.main().

## Execution route
- Route B - Codex loop.
- Why: GPT-6.1 decides interpretation and verifies evidence; Antigravity performs explicitly specified mechanical report edits.
- Close-out: deferred, separate Route B task after developer acceptance.

## Manual (developer does)
- [x] Developer approved this revised task on 2026-10-28. Open a fresh execution chat to run it.
- [ ] Independent review/acceptance and later close-out remain deferred.

## Agent (does on its own, once scope is confirmed)
- [ ] Confirm the v5 identity still binds current producer source, model revisions, and frozen development data; verify all protected v4 hashes.
- [ ] Verify 8/8 preflight and 720/720 full-development IDs, zero failures, CUDA/float32/TF32 metadata, score validity, and source-group membership. Check actual current artifacts rather than relying solely on previous verification claims.
- [ ] Derive a baseline-only report using cached traces and the unchanged BASELINE policy; evaluate no candidate policies. Include task/quality subgroups, source-group CIs, latency, peak allocated memory, raw token-length audit, and explicitly unavailable measures.
- [ ] Describe the raw token-length audit accurately: raw claim/context pairs over 512 tokens are not proof of actual model-input truncation after passage decomposition/selection.
- [ ] Report v4 versus v5 fairly: false alterations 386/399 in both; complete interception 240/321 to 239/321; residual errors 81 to 82. Explain that parser improvements did not meet the frozen false-alteration tradeoff.
- [ ] Give Antigravity the exact report wording, table data, source-log paths, and allowed edits. Forbid every shell/run_command call in its prompt. Preserve prior HANDOFF.md content verbatim.
- [ ] Include full unedited historical raw outputs from their saved logs with exact historical commands and known exit statuses. Do not fabricate missing output or imply that a historical command was rerun. Mark any unavailable historical command/output explicitly.
- [ ] Document the prior out-of-scope candidate-policy analysis and retain its raw evidence without adopting its selection result. Keep this deviation visible in the report.
- [ ] Verify the final report against the underlying artifacts and emit new completion-verification evidence. Record changed paths and limitations. Stop for the deferred review decision.

## Blocked on developer input
- None. Revised scope approved 2026-10-28. No data values or medical labels may be invented.

## Order
### Steps inside this task
1. Obtain approval and start a fresh Codex execution chat; read this file cold.
2. Verify existing identities, counts, score caches, metadata, and protected hashes. Halt on drift or incomplete evidence.
3. Prepare exact baseline-only report contents and mechanical Antigravity instructions. Check agy_list_jobs before agy_start_edit; cancel a running entry only if its process is confirmed dead.
4. Dispatch Antigravity with exact allowed paths, supported/default model, and an unconditional ban on all shell tools. GPT-6.1 retains interpretation and verification.
5. Verify the returned report, append raw verification evidence, and stop for independent review. Do not rerun the expensive inference solely because the inherited postprocessor emitted candidate metrics.

### Where this task sits
- Before this: parser fixes and targeted tests, 8-answer preflight, and complete 720-answer CUDA v5 run; original handoff incomplete following the incidental policy sweep.
- Next separately scoped task: Work Package 1, independent claim-level label audit, annotation policy, source-grouped splits, data/license provenance, and a genuinely untouched final holdout. Do not use guard predictions as gold labels.
- Then separately scope Work Package 2 evidence handling; Work Package 3 calibration/model comparison; Work Package 4 controlled Malayalam diagnosis; and Work Package 6 frozen combined final evaluation. Model/threshold selection follows reliable labels and evidence handling.
- A failed accuracy criterion is reported as a negative result, not relabeled as success. No production deployment is part of this program authorization.

## Verification required before this is considered done
- [ ] Fresh commands prove current producer/data/model identity and unchanged protected artifacts; paste full raw outputs and exit codes into HANDOFF.md.
- [ ] Exact selected development IDs and source groups match frozen membership; preflight has 8 unique IDs, full run has 720 unique IDs, no missing/extra IDs, zero reported failures, finite normalized score vectors.
- [ ] Run metadata proves CUDA, float32, TF32 off, and saved peak allocated GPU memory; distinguish recorded metadata from independently rerun inference.
- [ ] Baseline report reconciles with existing v4-v5 comparison and v5 baseline metrics, with denominators, subgroups, CIs, latency, and limitations.
- [ ] Research isolation: rg -n '(^|\s)from app\.' backend/research (exit 1 means no matches); record the actual command/output and normalized pass/fail result.
- [ ] Verify prior HANDOFF.md bytes remain an unchanged prefix and that full raw logs appear unedited in the appended evidence. Reconcile every claim and identify unavailable historical evidence.
- [ ] No source/test changes; all existing v4/v5 artifacts preserved; only explicit scoped report files changed.

## Flags (AGENTS.md rule triggers)
- Section 5.7: isolated research; verify import isolation.
- Section 5.8: current task completes only v5 reporting; remaining accuracy packages are separate tasks.
- Section 5.10: exact commands, raw stdout/stderr, exit codes, and identity evidence.
- Section 10: high-assurance/high-effort review because scoped generated report artifacts are under backend/research/ (legacy Opus 5/high).
- Section 12.5: halt on unexpected scope expansion, stale identities, protected-evidence mutation, private data, actual permission denial, or three repeated identical failures. The declared research-review trigger was explicitly authorized by the developer's prior Proceed instruction; retain its review assurance.
- Stale Claude Chat and fixed Antigravity-author sections remain superseded by the developer's global rules; do not edit AGENTS.md here.

## Suggested review tier (set at scoping time)
- High assurance, high effort - research evaluation evidence (legacy Opus 5/high). Preserve independent review; no claim of changed session effort.

## Executor
- Antigravity.
- Why: developer explicitly requested agy mechanical work while GPT-6.1 performs reasoning and verification.
- Antigravity model: bridge configured default; the current agy_start_edit schema accepts an omitted model. No external model name has been verified or invented.
- Bridge availability confirmed 2026-10-28; agy_list_jobs returned only done/cancelled jobs. Recheck immediately before each edit dispatch.
- Execution session: fresh Codex chat with GPT-6.1 for reasoning and verification; Antigravity edits only the specified report files. No direct implementation fallback if the bridge is blocked.

## Approval
- Status: APPROVED 2026-10-28 - developer approved revised scope in the planning chat. Execute in a fresh Codex chat with GPT-6.1 reasoning and Antigravity mechanical edits.
