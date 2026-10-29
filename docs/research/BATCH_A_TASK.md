# Current Task

## Feature
- Step 1 / Batch A: reconcile and reproduce the guard baseline from the supplied external handoff, establishing a trustworthy starting point without changing guard behaviour.

## Plan reference
- docs/research/GUARD_RESEARCH_PLAN.md, approved roadmap 2026-10-29, step 1 only.
- docs/research/FRIEND_START_HERE.md for portable context.
- docs/MASTER_PLAN.md section 3: isolated research and matched English/Malayalam reporting.
- docs/STATUS.md last updated 2026-09-22; stale research description acknowledged. Do not edit.
- Previous approved v5 task preserved at .agents/archive/CURRENT_TASK-v5-before-guard-roadmap-2026-10-29.md; its work is not implicitly completed or accepted.

## MASTER_PLAN.md update
- None in this task. Standing roadmap is linked through project instructions. Later documentation changes require their own scope.

## Files/areas in scope
- Read-only source snapshot: f88454133dc6a9811b78b5383641e8467c6acced (external guard-improvement handoff); independently confirm identity and actual code.
- Read-only original v5 reference and supplied public benchmark/cache artifacts, named explicitly in input manifest. Do not enumerate/load sealed holdout contents.
- New artifacts only: backend/research/results/guard-baseline-reconciliation-2026-10-29/ (input-manifest.json, environment.json, baseline-comparison.json, verification.log, limitations.md, SHA256SUMS.txt, necessary replay outputs).
- New portable, offline verification helpers only: backend/research/verification/guard_baseline_reconciliation/; no imports from production.
- HANDOFF.md: preserve existing bytes as prefix and append this task's full evidence.

## Explicitly out of scope
- New models, inference, downloads, threshold/policy sweeps, changes to labels/metrics/splits or guard source.
- Steps 2-9 of the roadmap; human annotation; any access to final holdout contents.
- Fixing inaccuracies in the baseline itself; document discrepancies and stop the affected reproduction.
- Formal acceptance, commits, pushes, PRs, deployments, STATUS.md or MASTER_PLAN.md changes.

## Do NOT touch
- backend/app/, frontend/, credentials, .env files, databases, Redis, private/patient data and backend/google_credentials.json deletion.
- All original result directories/caches/logs and unrelated dirty/untracked work.
- Rules, permissions, hooks, protected task/archive files during execution.
- Never execute backend.research.run_guard_nli_test.main(); no broad unittest discovery without inspecting what it invokes.
- Never merge/pull over the sender's dirty checkout, stash/reset its changes, or copy its credentials.

## Execution route
- Route B: coordinate, execute externally, independently review, developer decides.
- User-authorised executor exception: friend's external AI replaces default local Codex/Antigravity implementation for this research packet.
- Close-out deferred, separately approved Route B; no publishing in this task.

## Manual (developer does)
- [x] Developer approved this exact Batch A scope on 2026-10-29.
- [ ] Provide the friend this planning package and the existing handoff-bundle.zip/public evidence package; no broad workspace export.
- [ ] Accept or send back the independently reviewed result.

## Agent (friend's external AI after approval)
- [ ] Start a clean checkout of codex/guard-research-handoff-2026-10-29; record resolved HEAD and task hash. Verify backend/research content equals source baseline f88454133dc6a9811b78b5383641e8467c6acced before edits. Keep newer planning instructions; do not check out the old commit over them. Check main content when reporting merge status, never infer it from ancestry alone.
- [ ] Inventory hardware/software and required public inputs without opening sealed final data. Verify each input against the supplied manifest.
- [ ] Inspect replay commands/source for side effects, hard-coded paths and input dependencies. Use new scoped wrapper helpers for path binding; do not edit archived originals or guard logic.
- [ ] Determine whether caches bind the exact model, tokenizer, preprocessing, evidence and example identities. Record which claims are provable and which are not.
- [ ] Recompute old baseline and retained Fix 3 development metrics from valid cached evidence. Recompute previously-used validation only if its inputs and approved cached-only replay are available.
- [ ] Compare expected claims: development 386/399 to 376/399 clean altered and 239/321 complete interceptions; validation 193/207 to 187/207 clean altered and 129/153 complete interceptions. Preserve actual numbers on mismatch; no tuning.
- [ ] Inspect targeted research-only tests for safe offline execution; run relevant parser/replay tests only. Verify production/research import isolation in both directions.
- [ ] Save manifests, full logs, missing evidence, source/cache drift, exact commands and reproducibility instructions. Append root HANDOFF.md and stop for GPT-6.1 independent review.

## Blocked on developer input
- None for drafting. Execution requires approval and supplied artifacts. If absent at recipient: batch all missing inputs once; do not guess or substitute data.

## Order
### Steps inside this task
1. Read rules/roadmap/context and require APPROVED status; record packet version.
2. Inventory clean snapshot, input provenance and compute environment; do no inference.
3. Validate cache applicability and safe offline commands.
4. Perform bounded cached replays and targeted offline checks; capture all outputs.
5. Return one evidence package; coordinator GPT-6.1 independently checks it, Sol may check completeness, Astra only resolves scientific ambiguity.
### Where this task sits
- Before: unverified external improvement claims and unfinished historical v5 close-out/evidence state.
- After: Astra/GPT-6.1 define the scientific protocol and scope the next external batch; no automatic advance.

## Execution limits and halts
- Cached-only: zero model inference calls, zero paid calls, zero new model/dataset downloads.
- At most four full cached metric replays (baseline/Fix 3 x development/previously-used validation); rerun a failed replay at most once after an in-scope environment/path fix, total at most eight attempts.
- Offline command runtime budget 2 hours; additional generated output at most 2 GiB. At a limit, return progress and exact next action rather than expanding the budget.
- No exhaustive model/threshold search. Missing/incompatible cache or required unavailable dependencies: stop and report, do not substitute fresh inference or install globally.
- Halt on identity drift, protected artifact mutation, scope expansion, private data, actual permission denial, or a project mandatory halt. Do not bypass permissions.
- Minor reversible implementation choices within explicit scope may be made and logged without a round trip.

## Verification required before this is considered done
- [ ] Baseline SHA, snapshot inventory, input hashes and source/cache identities are evidenced with exact commands/raw outputs.
- [ ] Required input manifest entries are present or explicitly marked missing; final holdout not accessed.
- [ ] Development/used-validation results include IDs, source groups, denominators, before/after clean alteration, complete/partial interception definitions, retained/lost IDs where derivable, and all failures.
- [ ] Command outputs reconcile with saved result artifacts; differences from handoff claims are reported, not fixed away.
- [ ] Targeted offline test outputs and both isolation searches are included; no blanket "tests pass" assertions.
- [ ] Protected source/input hashes unchanged; original HANDOFF bytes unchanged as prefix; changed-file inventory stays inside scope.
- [ ] Model inference was not run; environment limitations and historical-vs-fresh evidence are explicit.
- [ ] Full raw logs, exit codes and SHA256 manifest delivered; future independent review remains required.

## Flags (AGENTS.md rule triggers)
- Sections 5.7/5.10: research isolation and exact evidence. Section 5.8: only baseline reconciliation, not all roadmap work.
- Section 10: research paths imply high assurance/high effort; escalate to xhigh if additional triggers actually arise. No downgrade because executor/model changed.
- Section 12.5 and all safety/data/privacy restrictions remain. User explicitly authorised friend as mechanical executor and Codex as planning/assessment coordinator.
- Legacy fixed-author and Chat routing are superseded for this research workflow by developer instructions; no permission bypass.

## Suggested review tier (set at scoping time)
- High assurance, high effort (legacy Opus 5/high), independent GPT-6.1 review for research evidence. This does not require Astra or establish a runtime effort setting.

## Executor
- Friend's external AI, manual portable handoff, explicitly requested by developer.
- Exact external provider/model unknown; record actual identity, do not invent it. No automatic local Antigravity or Codex implementation fallback.
- Fresh execution session on the friend's machine with a clean agreed checkout; coordinator stays in planning/review roles.

## Approval
- Status: APPROVED 2026-10-29 - developer approved Batch A in the planning chat. Execute in a fresh external AI chat on the friend's system; coordinator does not execute research here.

## Planning publication (coordinator only)
- Developer authorised a Git handoff on 2026-10-29 because the friend works on another system.
- Publish only planning/governance files on codex/guard-research-handoff-2026-10-29, based on origin/main; no PR, merge, research acceptance, STATUS update or implementation is implied.
- Explicit publication paths: AGENTS.md; .agents/AGENTS.md; .agents/CURRENT_TASK.md; .agents/archive/CURRENT_TASK-v5-before-guard-roadmap-2026-10-29.md; docs/research/GUARD_RESEARCH_PLAN.md; docs/research/FRIEND_START_HERE.md; docs/research/BATCH_A_TASK.md; docs/research/FRIEND_CHAT_PROMPT.md.
- This publication authorisation does not permit the friend to commit/push research results or expand Batch A.
