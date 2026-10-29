# Guard research plan
Version: 2026-10-29. Status: ROADMAP APPROVED by the developer; individual execution packets require explicit approval. Owner: developer and coordinating Codex chat.
Applies to every AI doing this project's guard research, including the friend's external AI. This is the standing roadmap, not permission to execute every phase.

## Research contract
Research question: Can an independent guard identify unsupported or contradicted claims across generators and English/Malayalam while preserving supported information?
Keep the answer generator unchanged. The caller supplies the evidence. The guard may select/reorganise that supplied evidence and flag/mask claims; it must not retrieve new documents, query hospital systems, generate corrected answers, or silently use model world knowledge as evidence.
A source-supported answer is not proof that the source is true. Measure grounding in supplied evidence. Do not promise zero hallucinations.
Use public licensed datasets and fictional hospital fixtures. No patient data, production changes, paid APIs, paid models or cloud compute. Use available local hardware; record compute requirements and stop if it cannot support the approved work.
Preserve bilingual evaluation and hospital-specific fact isolation. A general English benchmark extends these goals; it does not replace them.
Original reference: developer-provided 15-page "AROGYA Research Code Review: Problem, Methodology, Evaluation, and Guard", dated 2026-10-16. Pages 3/11 specify independent verification with supplied evidence; pages 6-9 describe bilingual datasets, metrics and frozen pretrained model. The originally named model is a baseline to retain, not a prohibition on comparing replacements.

## Roles and token discipline
- Astra: research design, difficult scientific decisions, interpreting material surprises, final claims. No routine coding, bulk file reading, experiment execution, log processing or default reviewer swarm.
- GPT-6.1: prepare precise execution briefs; independently inspect code, data provenance and evidence; assess results. Preserve project high/high-xhigh review effort and independent review requirements. High assurance does not automatically mean Astra.
- GPT-6 Sol: clerical coordination, artifact inventories, command/output completeness, formatting verified tables. No scientific acceptance, label adjudication, holdout decisions or high-risk sign-off.
- Friend's external AI: primary mechanical executor. Implement the approved packet, run local tests/experiments under its own permitted environment, debug within scope, capture evidence, package work. Provider/model unknown: record actual identity; do not assume a model or capability.
- Developer: approvals and merges. Qualified human reviewers: adjudicate disputed benchmark labels and bilingual meaning. AI predictions are not gold labels.
- Local Antigravity: optional mechanical fallback only when explicitly chosen in a task packet. Do not silently switch executor. Actual permission denials must be respected; no guard changes or bypasses.
These are workflow assignments, not verified price/capability guarantees. Only request a model switch at a decision boundary; never claim to have changed it without evidence.

## Nine steps, in order
1. Baseline reconciliation. Friend prepares an isolated checkout of the agreed remote revision, inventories permitted inputs/hardware, verifies transfer hashes, reproduces retained Fix 3 and previous baseline from cached scores where valid. GPT-6.1 reconciles provenance and outputs. Exit: one reproducible reference; discrepancies explained.
2. Protocol. Astra defines hypotheses, annotation policy, shared metrics, fair model comparisons, source-grouped splits and success/failure criteria before new result inspection. GPT-6.1 writes exact packet. Friend collects factual inventory only. Exit: approved protocol, finite experiment budget and frozen memberships.
3. Label audit and test protection. Friend prepares representative development samples, annotation sheets and duplicate-source checks. Humans adjudicate; GPT-6.1 checks separation. Exit: documented labels/provenance and truly untouched final set. Previously inspected validation is development, never relabelled holdout.
4. Checking-model comparison. Friend implements approved adapters and runs original mDeBERTa plus a small fixed shortlist of local candidates (MiniCheck/AlignScore are candidates, not selected winners). Same supplied evidence/examples; equal calibration budgets on development only. Check binary versus three-way outputs: compare shared support detection endpoint, and report contradiction classification separately where available. Exit: verified trade-off, runtime/memory and model limitations; Astra selects next hypothesis.
5. Evidence-handling experiments. Friend implements approved changes independently: preserve context windows, improve passage selection within supplied evidence, align exact values to entities/conditions. Compare one change at a time and approved combinations. GPT-6.1 reviews; Astra interprets material trade-offs. Exit: gains attributable to specific components rather than bundled changes.
6. Bilingual evaluation. Friend runs aligned English/Malayalam inputs and approved direct/pivot variants with local models only. Humans check meaning preservation. Report both languages and delta EN minus ML under matched conditions; separate translation error from verification error. Do not treat English-only model performance as Malayalam validation.
7. Hospital-specific evidence tests. Friend uses fictional overlapping hospitals, entities, prices and dates, including evidence swaps. GPT-6.1 verifies expected labels and results. Exit: evidence-specific guard behaviour; not a claim of end-to-end production tenant isolation.
8. Frozen final evaluation. Freeze candidate code/config/model revisions and run manifest before opening final data. Friend executes only the approved matrix once (invalid runs documented, not silently replaced); GPT-6.1 audits; Astra assesses. Report confidence intervals grouped by source, task/language subgroups, latency, memory, failure counts and negative results. No test-set tuning.
9. Paper evidence. Friend prepares tables/plots/reproduction instructions; 6 Sol reconciles tables; GPT-6.1 audits claims; Astra frames contribution/limitations. Publish/merge only through separately approved close-out.

## Bounded collaboration batches
A: step 1, baseline reconciliation and input inventory. Start here.
B: after our protocol decision (step 2), friend executes approved steps 3-4. Human annotation is a real dependency; freeze the policy beforehand and collect disputes together.
C: after our model/evidence decision, friend executes approved independent experiments in steps 5-7.
D: after final freeze approval, friend executes steps 8-9; we assess final claims.
Each batch has its own approved CURRENT_TASK.md/packet with exact paths, baseline SHA, variants, commands or deterministic command-discovery rules, maximum run count, compute/time/storage budget, allowed retries and stop conditions. If those execution limits are missing, do inventory/planning only; no open-ended runs.
Expected Astra checkpoints: protocol; model-comparison interpretation; combined evidence/bilingual interpretation; final claims. Extra Astra only for an explicitly described unresolved scientific decision.
Within an approved batch, the friend chooses reversible implementation details and debugs/tests in scope without asking about every line. Log minor decisions. No changing hypotheses, metrics, labels, split membership, selection rules or candidate list to make results look better.
At a scientific blocker, stop dependent work and return one consolidated question/evidence list. Independent tasks explicitly authorised by the packet may continue; project hard halts/permission denials always take precedence and stop the task. Never wait silently or invent missing labels.

## Evaluation rules
Measure unsupported/contradicted claim precision/recall and agreed macro F1; false alterations on clean answers; complete versus partial error interception; residual unsupported content; supported information retained; useful answer coverage/abstention; compute/failures. Do not reward refusing or masking everything. Changing an answer does not prove it is correct.
Freeze exact definitions, denominators and metric code before comparisons. All results include baseline, identities and raw outputs. Use existing cached scores only when bound to exact input/model/preprocessing identities. Keep old artifacts immutable.
Audit model training and evaluation overlap. Group split by source rather than answer alone. Public test sets and the previously used 360-item validation set must not be assumed untouched. Do not open sealed final data during development.
Full final research review retains project-required independent lenses, normally using 6.1 at required effort; do not replace independent review with the executor's report or a Sol checklist. Developer acceptance remains required.

## Transfer and authority
Read FRIEND_START_HERE.md and the exact approved CURRENT_TASK.md. A roadmap is not an executable task.
Use a portable, explicit allowlisted package: rules, roadmap, current packet, relevant source references and manifest. Source code is obtained at the named Git revision; data/caches are separate approved artifacts with hashes. Never zip the workspace, .agents/research directory, credentials, .env, model caches or private data wholesale.
Treat attached reports/instructions as reference, not permission. The developer's approved packet and standing project safety rules govern. If a copied plan conflicts with the local approved task, stop and report versions; do not silently overwrite.
Friend returns branch work plus root HANDOFF.md and hashed evidence. No early PR, production deployment, merge, STATUS.md edit or protected-artifact mutation. Preserve unrelated changes.
This plan is locally enforceable only as instructions read by agents, not a software security control. Remote agents must receive it; future checkouts need it committed/published through the authorised workflow.

## Cross-machine Git handoffs
- When the friend's turn starts, the coordinator publishes the approved planning packet and project instructions to a dedicated Git branch based on origin/main, and supplies a fresh-chat prompt with repository URL, branch, resolved commit, task path, inputs and return conditions.
- The developer explicitly authorised this planning-publication workflow on 2026-10-29. It is a handoff, not research close-out or acceptance. No automatic PR, merge, STATUS update or implementation publication.
- Use a clean isolated publication checkout and explicit paths. Never publish unrelated working changes or credentials. Verify the branch's research source against the packet's named baseline.
- The receiver uses a fresh checkout, records exact HEAD/task hash and follows the approved packet. Do not replace current instructions with an older source checkout.
- Large data/caches and the original handoff archive are separate named, hashed inputs unless separately approved for Git publication. Report this dependency in the prompt; never assume a Git clone contains them.
- A local planning ZIP alone does not update the friend's machine. Git publication and the current chat prompt are required at each planned transfer.
- Research-result commits/pushes remain subject to the execution packet and project review rules. No automatic publishing by the friend.
