# Start here: external research executor
Version: 2026-10-29. Audience: the developer's friend and their AI.
You perform implementation and experiment mechanics. The coordinating AI/developer owns research design, interpretation and acceptance. No previous chat is needed.

## Read in this order
1. AGENTS.md and .agents/AGENTS.md.
2. docs/research/GUARD_RESEARCH_PLAN.md.
3. .agents/CURRENT_TASK.md, including approval, executor, boundaries and stop conditions.
4. The reference/context below and only the source files necessary for the approved packet.
If the task is DRAFT, inspect the packet and report missing inputs, but do not implement or run experiments. Request approval from the developer; the roadmap is not approval.
When a transfer bundle is used, extract to a separate folder and compare task/rule versions before installation. Never overwrite an existing task or dirty checkout automatically.

## Research context
The original work evaluates an independent, non-generative guard for supplied evidence. Main languages: English and Malayalam. Original checker: MoritzLaurer/mDeBERTa-v3-base-mnli-xnli plus claim splitting, exact-value checks and flag/mask policy. Preserve original generator outputs. Do not retrieve outside evidence or rewrite answers.
The original October 16 reference had 100 guard-development items (50 English/50 Malayalam; 50 tuning/50 holdout), plus fictional hospital fixtures. Do not equate those results with later public-benchmark results.
Later research uses RAGTruth; study generalisation without dropping bilingual and hospital-isolation questions.

## Current factual status and uncertainties
Fetched on 2026-10-29: origin/guard-improvement f88454133dc6a9811b78b5383641e8467c6acced; origin/main 65865af738b92a2ea3e4b1347a4e495b6292aa3c records PR #45. Recheck remote/content and identities; merge log alone is not content verification.
Sender's checkout was feat/iris-ease-health-redesign at bc01b98093cda5682a3e1c970de056d29d0b8f9e, with overlapping uncommitted research work and unrelated files. Do not pull/merge over it, stash it or reset it.
External handoff claims: retained Fix 3 skips non-claim fragments; fixes 1/2/5 reverted and threshold fix 4 not applied. Development: clean altered 386/399 to 376/399, complete interception 239/321 unchanged. Validation: clean altered 193/207 to 187/207, interception 129/153 unchanged. These have NOT been independently reproduced by the coordinator.
The 360-answer validation split was previously used for selection. The claim that a final test split stayed sealed needs provenance; do not open it to investigate.
A 60-item audit was synthetically labelled, not human ground truth. Do not use it as independent labels.
The old approved v5 reporting task is preserved separately, not declared complete by replacement.
docs/STATUS.md is dated 2026-09-22 and stale relative to this research. Do not change it or treat it as evidence newer experiments did not occur.
Reference transfer supplied by developer: handoff-bundle.zip, includes git bundle, cached scores, scripts and SHA256 manifest. It is NOT included in the planning-only package. Request this exact approved artifact if absent, not access to the sender's entire workspace. Its scripts may contain another machine's hard-coded paths. Source/inputs must be inspected before execution.
Original PDF is likewise not bundled; the roadmap records the relevant contract. Ask for it only if an ambiguity actually depends on its contents.

## Working agreement
Operate in your own clean isolated checkout, under your own actual tool permissions. No permission/guard bypass, credentials changes, paid services or production access.
Batch questions at startup: missing artifact, incompatible environment, contradictions. Choose minor reversible coding details yourself within scope. Preserve exact data labels and split identities. Stop at packet limits; no unbounded sweeps or opportunistic fixes.
The first packet is baseline reconciliation only. Future experiments require a new approved packet. Write one consolidated report per batch, not a request after every routine action.
Do not dispatch messages or publish branches/PRs unless that packet explicitly authorises it.

## Return package
1. Work on an agreed branch (or explicit patch snapshot where commits are not yet allowed), baseline SHA, reviewed snapshot SHA/hash, full changed/untracked inventory. No pre-review commit if project rules prohibit it.
2. Root HANDOFF.md: <=1-page decision summary followed by complete raw evidence sections.
3. For each verification requirement: exact working directory and command, raw stdout/stderr, exit code, touched/output files. Separate historical logs from commands actually rerun. Failures and missing evidence remain visible.
4. Run manifest: dataset IDs/splits/source groups/hashes, model/tokenizer revisions, dependency versions, parameters/seeds, device/dtype, resource usage, cache identity, actual executor/model identity if available.
5. Results tables with denominators and baseline deltas; all per-example traces required by the packet; provenance; limitations; minor decisions and deviations.
6. SHA256 artifact inventory, reproducibility instructions using portable relative paths, concise unresolved questions. No secrets/private data.
The coordinator independently reviews this package. Your "passed" statement is not acceptance.

## Current cross-machine entry point
Batch A was approved on 2026-10-29. Obtain codex/guard-research-handoff-2026-10-29 from the repository; docs/research/FRIEND_CHAT_PROMPT.md contains setup and the exact start prompt.
The handoff branch is based on main with research content matching f88454133dc6a9811b78b5383641e8467c6acced. Keep the new planning files in the checkout and verify that source comparison before work.
The separate handoff-bundle.zip may already exist on your system. If absent, request that named artifact once. The repository does not include its cached evidence automatically.
