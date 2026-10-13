# Method Facts & Experimental Inventory

This file records the exact configurations, model checkpoints, parameters, and numbers reported in the AROGYA Grounding Guard research, tracing each metric back to its executable script or fixture file.

---

## 1. Models & Hardware Environment

| Component | Model Checkpoint | HuggingFace Identifier | Precision / Device | Source File |
|---|---|---|---|---|
| **Multilingual NLI Scorer** | mDeBERTa-v3-base-mnli-xnli | `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` | FP32 / CPU & CUDA (fallback) | [`backend/research/guard/nli.py`](file:///e:/AROGYA_REAL/backend/research/guard/nli.py) |
| **Malayalam-English Translator (Pivot)** | MarianMT ml-en | `Helsinki-NLP/opus-mt-ml-en` | FP32 / CPU | [`backend/research/run_guard_nli_test.py`](file:///e:/AROGYA_REAL/backend/research/run_guard_nli_test.py) |
| **Production Generator** | GPT-4o-mini | `openai/gpt-4o-mini` | API (temperature=0.0) | [`docs/MASTER_PLAN.md`](file:///e:/AROGYA_REAL/docs/MASTER_PLAN.md) |
| **Local Runtime** | Python 3.13, PyTorch 2.14.1+cu130 | Local Virtual Environment | Windows x86_64, NVIDIA RTX GPU | `backend/venv/` |

---

## 2. Benchmark Datasets and Samples

| Dataset | Size / Sample | Languages | Phenomena Types | Source Path |
|---|---|---|---|---|
| **AROGYA Bilingual Dev Set** | 100 items (50 tuning, 50 holdout) | 50 English, 50 Malayalam | 11 distinct clinical & scheduling phenomena | [`backend/research/fixtures/guard_dev_set.json`](file:///e:/AROGYA_REAL/backend/research/fixtures/guard_dev_set.json) |
| **RAGTruth QA Public Subset** | 300 items (fixed sample, seed 20261007) | English | Question answering with retrieved web/news snippets | [`backend/research/public_eval/loader.py`](file:///e:/AROGYA_REAL/backend/research/public_eval/loader.py) |
| **Synthetic Conflict Suite** | 40 hand-crafted pairs (20 with conflict, 20 without) | English & Malayalam | `instruction_vs_data`, `answer_vs_data`, `answer_follows_instruction_against_data` | [`backend/research/guard/conflict_cases.jsonl`](file:///e:/AROGYA_REAL/backend/research/guard/conflict_cases.jsonl) |
| **Synthetic Fact-Lock Suite** | 40 hand-crafted clinical sentence pairs | English & Malayalam | `number`, `price`, `time`, `date`, `weekday`, `doctor_name`, `test_name` | [`backend/research/guard/factlock_cases.jsonl`](file:///e:/AROGYA_REAL/backend/research/guard/factlock_cases.jsonl) |

---

## 3. Calibrated Classification Thresholds

Calibrated strictly on the 50-item tuning half (`guard_dev_set.json`) without inspecting holdout examples:

- **English Direct NLI:**
  - Entailment threshold: `0.70`
  - Contradiction threshold: `0.40`
- **Malayalam Direct NLI:**
  - Entailment threshold: `0.55`
  - Contradiction threshold: `0.45`
- **Malayalam Translation Pivot (via MarianMT):**
  - Entailment threshold: `0.65`
  - Contradiction threshold: `0.35`
- **Source Configuration:** [`backend/research/guard/thresholds.json`](file:///e:/AROGYA_REAL/backend/research/guard/thresholds.json)

---

## 4. Key Experimental Metrics Traceability

| Claim / Metric | Value | Verification Script / Test |
|---|---|---|
| **Claim Splitter Tuning Recall (EN)** | 100.0% (29 / 29 facts) | `python -m backend.research.run_guard_claims_test` |
| **Claim Splitter Tuning Recall (ML)** | 100.0% (28 / 28 facts) | `python -m backend.research.run_guard_claims_test` |
| **Conflict Detector Precision / Recall** | 0.783 Precision, 0.900 Recall | `backend/venv/Scripts/python.exe -m backend.research.run_guard_conflict_test` |
| **Fact-Lock Accuracy** | 100.0% (40 / 40 test cases) | `python -m backend.research.run_guard_factlock_test` |
| **Baseline Method (G-12)** | 5 passed, 0 failed | `python -m backend.research.run_baseline_test` |
| **Public Eval Dry Run (G-04)** | 4 passed, 0 failed | `python -m backend.research.run_public_eval_test` |
| **Public Eval Evaluation (G-13)** | 3 passed, 0 failed | `python -m backend.research.run_public_eval_evaluation_test` |
| **Part D Evaluation Pipeline (G-14)** | 4 passed, 0 failed | `backend/venv/Scripts/python.exe -m backend.research.run_part_d_test` |
| **Real Query PII Scrubber (G-15)** | 3 passed, 0 failed | `python -m backend.research.run_anonymise_test` |
| **Benchmark Release Pack (G-16)** | 4 passed, 0 failed | `python -m backend.research.run_release_test` |
| **Research Isolation Check** | 0 violations | `python -m backend.research.check_isolation` |
