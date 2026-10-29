# Friend chat prompt - approved Batch A
Use this prompt in a fresh chat on your own system after obtaining the repository and the original handoff-bundle.zip if it is not already available.

## Repository setup
Repository: https://github.com/Gotham28/hospital-ai-platform
Handoff branch: codex/guard-research-handoff-2026-10-29

For a NEW checkout only:
    git clone --branch codex/guard-research-handoff-2026-10-29 --single-branch https://github.com/Gotham28/hospital-ai-platform.git hospital-guard-batch-a
    cd hospital-guard-batch-a

Do not run clone into an existing directory or pull/switch/reset a dirty checkout. Use a fresh directory. Record the resolved HEAD SHA before starting. GitHub authentication must use your own authorised account; never ask for the sender's credentials.

## Paste into your AI chat
You are the mechanical executor for the AROGYA guard research project. Our coordinating AI/developer handles research design, interpretation and acceptance. Implement and execute only the approved Batch A packet; you do not need the previous chat.

Read in order:
1. AGENTS.md and .agents/AGENTS.md
2. docs/research/GUARD_RESEARCH_PLAN.md
3. docs/research/FRIEND_START_HERE.md
4. .agents/CURRENT_TASK.md

Confirm the task is APPROVED for Batch A, and record the task file hash and checkout HEAD. The source baseline is f88454133dc6a9811b78b5383641e8467c6acced. The handoff branch contains the same backend/research source plus newer planning instructions. Before changing anything, verify that equality with:
    git diff --quiet f88454133dc6a9811b78b5383641e8467c6acced HEAD -- backend/research
Exit 0 is expected. Do not check out the old commit over the new instructions. Stop and report if research content differs.

Locate the original handoff-bundle.zip or its exact manifest-verified extracted contents on your machine. This input is separate from Git; do not download arbitrary replacements or inspect sealed final-test contents. Collect genuinely missing inputs into one message before any experiment.

Execute Batch A: inventory and verify public inputs/environment, validate cached-score identity, reproduce the old baseline and retained Fix 3 metrics using cached evidence only, run the targeted safe offline checks, and produce the specified evidence package. No new inference, models, downloads, paid services, new scientific experiments or production changes.

Within approved paths, handle reversible path/environment fixes independently and record them. Do not change guard behaviour, labels, split membership, metrics, or thresholds to match expected results. Do not bypass actual tool permissions. Observe the exact run/time/storage budgets and hard halts in CURRENT_TASK.md. Return partial evidence and one consolidated blocker list if a mandatory input is missing; never claim completion.

Finish with work on the local branch or a portable patch snapshot, the root HANDOFF.md preserving its previous bytes, full raw command outputs and exit codes, JSON results, hashes, and a concise summary of discrepancies and decisions. No commit/push/PR is authorised for the research execution packet. Return the package to the developer for GPT-6.1 independent assessment. Stop after Batch A; do not advance to model comparisons.
