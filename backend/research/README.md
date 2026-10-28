# Research

## How to run
Any module in this package must be run from the repository root using the `backend/venv` virtual environment (e.g. `backend\venv\Scripts\python -m backend.research.<module>` on Windows). This package is never run as a standalone script from inside its own directory — always run it as `-m backend.research.<module>` from the repo root.

## Two-way isolation rule
The research package enforces a strict two-way isolation boundary: nothing under `backend/app/` may import anything from `backend/research/`, and nothing under `backend/research/` may import anything from `backend/app/`. All research code must be runnable standalone. To verify this rule, an automated check is available. Run it using `python -m backend.research.check_isolation`.

## API keys
API keys for this package live in `backend/research/.env` (see `.env.example` for the variable names — `OPENAI_API_KEY`, `GROQ_API_KEY`). This file is strictly local and must never be committed to the repository.

**Note:** never commit `.env`.

## Local grounding-guard performance

The guard is research-only. Run from the repository root, with a dedicated
Python 3.11 environment; the application environment is not modified:

```bat
py -3.11 -m venv backend\research\.venv
backend\research\.venv\Scripts\python.exe -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
backend\research\.venv\Scripts\python.exe -m pip install -r backend/research/requirements-guard.txt
backend\research\.venv\Scripts\python.exe -B -u -m backend.research.run_guard_performance --setup
backend\research\.venv\Scripts\python.exe -B -u -m backend.research.run_guard_performance --suites
backend\research\.venv\Scripts\python.exe -B -u -m backend.research.run_guard_performance
```

Setup downloads only the existing public NLI model
`MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` and Malayalam-to-English model
`Helsinki-NLP/opus-mt-ml-en` into `backend/venv/model_cache/`. Setup uses IPv4
HTTPS to avoid the observed Windows-network connection resets, with TLS
certificate verification enabled and no system-network changes. It needs internet
but no paid API or application credentials. Inference disables model downloads
and blocks socket connections. Do not run `run_guard_nli_test` to reproduce
performance: its main function retunes and overwrites thresholds.

Outputs are in `backend/research/results/guard-performance-2026-10-26/`;
the readable report is `notes/guard_performance_2026-10-26.md`. Each mode
preserves its complete output and exit code. The run records package versions,
model revisions, fixture/threshold hashes and case-level predictions. Keep the
environment, models and bulk generated results untracked.

Setup pins the recorded model commits (`8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c`
and `ab043b0bded4c755ef79e30a8189085a17fe82ca`) and sets only their generated
cache references to those snapshots. Inference refuses reference drift. Use
`python -B -m backend.research.run_guard_performance --verify-cache` with the
research interpreter to check pins without network or inference. Exact resolved
dependency versions are saved in `pip-freeze.txt` alongside the run evidence.

Holdout metrics are primary; all-100 and tuning results are descriptive. The
report separates claim classification, answer-error detection, full gold-error
span redaction, unnecessary alterations, conflict types, target fact-lock status
and CPU latency. A changed answer is not evidence of correction. Claim alignment
groups complete source fragments and counts missing/ambiguous extraction as a
miss. The old splitter recall test accepts substrings, so its 100% result can
include fragments such as `Dr.` and does not establish full extraction accuracy.

The 40 fact-lock cases cover synthetic aliases and selected target statuses;
they do not prove general name transliteration, entity attribution, dates or
numbers. Synthetic evaluation does not establish clinical safety, real-world
generalization or production performance. None of these commands load research
`.env` files or call paid providers.

## Public external guard benchmarks

The approved external benchmark uses the official XNLI English test and
IndicXNLI Malayalam forward-test translations (5,010 aligned pairs per language),
plus all 2,700 RAGTruth test answers. Dataset and upstream adaptation-code
revisions are pinned in `run_guard_external.py`; downloaded source hashes,
attribution and validation counts are saved under
`results/guard-external-2026-10-26/`. Public source files are read as data;
downloaded Python loaders are retained as provenance text and never executed.
The original XNLI archive contains development files, but only its test TSV is
read for scoring. IndicXNLI training/development files are never downloaded.

Run from the repository root after the existing guard model setup:

```bat
backend\research\.venv\Scripts\python.exe -B -m backend.research.run_guard_external_test
backend\research\.venv\Scripts\python.exe -B -u -m backend.research.run_guard_external --download
backend\research\.venv\Scripts\python.exe -B -u -m backend.research.run_guard_external --validate
backend\research\.venv\Scripts\python.exe -B -u -m backend.research.run_guard_external --evaluate --limit 3 --run-name preflight
backend\research\.venv\Scripts\python.exe -B -u -m backend.research.run_guard_external --evaluate --run-name full-cuda --device cuda
backend\research\.venv\Scripts\python.exe -B -u -m backend.research.run_guard_external --report --run-name full-cuda
```

`--download` is the only network stage. Evaluation verifies the existing pinned
model cache, forces offline mode and blocks socket connections. Model weights,
guard algorithms, original fixtures and thresholds remain fixed. No `.env`,
hospital database, application service or paid API is used.

The full run executes 22,740 conditions: raw NLI and assembled guard for each
language (20,040 conditions), plus 2,700 RAGTruth guard outputs. The English and
Malayalam inputs represent the same 5,010 semantic pairs, with 1,670 unique
premises. RAGTruth has 450 source groups, each with six model answers. These
are correlated observations; confidence intervals resample source groups,
and bilingual gap intervals resample corresponding groups together.

Raw NLI uses the original same-language premise/hypothesis. The assembled
Malayalam guard uses the aligned English premise and Malayalam hypothesis,
matching its existing claim-only translation pivot. Whole-hypothesis labels
are scored at answer level; fragments never inherit invented gold labels.
XNLI development examples were used to train this mDeBERTa checkpoint and are
excluded. Its published model card already reports XNLI test performance;
this is an established benchmark, not an unseen private evaluation.

RAGTruth contexts preserve the published source field intact. The adapter
removes the exact evidence block from the original prompt and passes the
surrounding original instructions separately. Gold labels and annotation
comments are never inference inputs. Primary metrics use all test answers
and all published error spans, including `implicit_true` and `due_to_null`;
quality, task, generating-model and annotation-policy sensitivities are
reported separately. Gold-free text is not a complete claim-by-claim label
set. Conflict/fact-lock outputs are retained, but their accuracy is unavailable
without corresponding gold labels.

Detection is whether the claim-check stage flags any unsupported/contradicted
fragment; it is separate from complete error-span interception. Character
overlap includes whitespace to match the published scoring definition.
Removing an entire claim can also remove correct content. Redaction never
establishes a factual correction or readable final answer.

Evaluation is serial and uncached, with four PyTorch CPU threads. Its timing
includes a second tokenization used to measure truncation; fixed artificial
warm-up is excluded. The guard still truncates NLI pairs at 512 tokens, and
long RAGTruth contexts can lose relevant evidence. This limitation is measured
without adding context chunking or changing the model. The full run can take
roughly a day on CPU; fixed preflight counts are not representative
performance estimates.

The developer requested the available RTX 3050 Laptop GPU (4 GB) during this
run. The initial CPU-only PyTorch was replaced with the official CUDA build of
the same version in the isolated environment:

```bat
backend\research\.venv\Scripts\python.exe -m pip install --upgrade --no-deps torch==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128
backend\research\.venv\Scripts\python.exe -B -u -m backend.research.run_guard_external --evaluate --limit 3 --run-name preflight-cuda --device cuda
```

The install uses process-local IPv4 HTTPS after default-route resets, with
certificate verification enabled. The runner loads the original float32
tensors on CPU then moves them directly to CUDA. It disables TF32 and does
not use fp16, preserving weight precision. CPU and CUDA timings are separate;
the interrupted `full/` CPU run is partial evidence and must not be combined
with `full-cuda/` outputs. The pinned wheel index follows the official PyTorch
instructions: https://pytorch.org/get-started/previous-versions/ .

The same full-run command resumes complete JSONL records after interruption.
It rejects changed dataset/code/model/threshold/option identities, duplicate
keys or unknown IDs. Do not truncate a partially written line or edit a run
manifest to force resumption; preserve the run and investigate. Incremental
`--report` output describes completed rows and must be checked against
`completion.json` before claiming the full evaluation is complete.

XNLI and IndicXNLI substantive terms restrict dataset use to noncommercial
research under CC BY-NC 4.0; IndicXNLI's conflicting CC0 metadata does not
replace that restriction. RAGTruth's repository is MIT; retain upstream source
notices. Keep raw corpora and bulk results local and untracked. Cite the
original XNLI, IndicXNLI and RAGTruth papers. These general-domain datasets do
not establish clinical safety or hospital-domain Malayalam performance.

## English action-policy calibration (2026-10-27)

`run_guard_calibration.py` evaluates redaction decisions after the existing NLI
verdict. It uses only pinned RAGTruth **train** answers, with a deterministic
source-group split: 720 development answers (120 groups) and 360 reserved
validation answers (60 groups). The same cached per-claim verdicts, NLI
probabilities and exact-rule provenance replay all ten predeclared policies.
The original full public test results remain in
`results/guard-external-2026-10-26/full-cuda/`.

No candidate met the frozen tradeoff on development, so
`action_policy.ACTIVE_ENGLISH` remains `BASELINE`. The validation split was
scored for baseline characterization only. There is no promoted candidate or
candidate public-test run. See
`notes/guard_action_policy_2026-10-27.md` and
`results/guard-action-policy-2026-10-27/` for counts, confidence intervals,
token truncation and the complete selection record. In guard output, English
claims now carry `altered` alongside the unchanged detection `verdict`.
The original `*-traces.jsonl` and first `*-v2-traces.jsonl` files remain
historical records. Review found that v2 omitted a live guard-wrapper
dependency. The authoritative rerun uses `*-v3-traces.jsonl` with identities
that bind the manifest, scorer/guard/adapter/replay code, pinned model
revisions, library versions, device and precision. Resume, replay, token audit
and verification reject missing or drifted v3 identities. Full inference
stdout/stderr is captured in `*-v3-inference.log`.

From the repository root, use the research Python environment:

```bat
backend\research\.venv\Scripts\python.exe -B -m unittest backend.research.guard.action_policy_test backend.research.run_guard_calibration_test backend.research.run_guard_external_test
backend\research\.venv\Scripts\python.exe -B -u -m backend.research.run_guard_calibration --split development --device cuda
backend\research\.venv\Scripts\python.exe -B -u -m backend.research.run_guard_calibration --split development --audit-tokens
backend\research\.venv\Scripts\python.exe -B -u -m backend.research.run_guard_calibration --split validation --device cuda
backend\research\.venv\Scripts\python.exe -B -u -m backend.research.run_guard_calibration --split validation --audit-tokens
backend\research\.venv\Scripts\python.exe -B -u -m backend.research.run_guard_calibration --verify
```

The calibration run is offline and resumable, but do not change its manifest or
identity files to force a resume. Validation is not a tuning set. The public
XNLI/IndicXNLI and RAGTruth test labels were inspected in the preceding
benchmark, so any later public-test comparison is exploratory.
