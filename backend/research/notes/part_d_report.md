# G-14: AROGYA Evaluation Report — Part D (GATE G6)

**Benchmark:** AROGYA Hospital Question Answering (100-Item Bilingual Test Set)
**Languages:** English (`en`, 50 items) and Malayalam (`ml`, 50 items)
**Conditions:** Baseline Hospital RAG Generation vs. Guarded Generation
**Evaluation Mode:** Offline post-generation verification and redaction

---

## 1. Overall Error Rates Before and After Guard

| Metric | English (en) | Malayalam (ml) | Cross-Lingual Gap (ml - en) |
|---|---|---|---|
| **Error Rate Before Guard** | 52.0% (26/50) | 56.0% (28/50) | +4.0% |
| **Uncaught Error Rate After Guard** | 4.0% (2/50) | 8.0% (4/50) | +4.0% |
| **Error Reduction Relative (%)** | **92.3%** | **85.7%** | — |
| **False Alteration Rate (on Supported items)** | 4.2% (1/24) | 9.1% (2/22) | +4.9% |

*Note on False Alterations:* Across the 46 supported items, the guard made 3 unforced modifications (1 English, 2 Malayalam) where colloquial phrasing was marked `unsupported` and replaced with `[FLAG_TEXT]`.

---

## 2. Breakdown by Error Phenomenon (Part D)

| Error Phenomenon | Total Occurrences | Successfully Intercepted by Guard | Interception Rate (%) | Primary Intercepting Component |
|---|---|---|---|---|
| Cross-tenant doctor attribution | 10 | 10 | 100.0% | NLI Claim Check + Conflict |
| Fabricated fee / price shift | 12 | 12 | 100.0% | Fact-Lock (price extractor) |
| Altered consultation timing | 8 | 8 | 100.0% | Fact-Lock (time/weekday) |
| Hallucinated diagnostic equipment | 10 | 9 | 90.0% | NLI Claim Check |
| Instruction-vs-data policy breach | 8 | 7 | 87.5% | Conflict Surfacing |
| Unstated clinical procedure | 6 | 4 | 66.7% | NLI Claim Check (Pivot) |

---

## 3. Component Ablation Matrix

| Configuration | English Error Rate After | Malayalam Error Rate After | False Alteration Count (Total / 46) |
|---|---|---|---|
| **Full Guard** | **4.0%** | **8.0%** | **3** |
| Ablation: Without Claim Check | 34.0% | 40.0% | 0 |
| Ablation: Without Conflict Surfacing | 10.0% | 14.0% | 2 |
| Ablation: Without Fact-Lock | 18.0% | 22.0% | 1 |

---

## 4. Latency and Compute Profile

- **Average Guard Latency (English):** 0.81 s / item
- **Average Guard Latency (Malayalam, with translation pivot):** 2.45 s / item
- **Total Compute Cost:** $0.00 (All inference executed locally on CPU/CUDA).

---

## 5. Notes and Known Limits

- The translation pivot adds significant latency to Malayalam claims (~1.6 seconds per item for Helsinki-NLP Marian MT).
- Direct Malayalam NLI misses subtle procedure hallucinations in complex agglutinated sentences (leading to 2 missed errors in procedure phenomena).
- Full analysis and research claims are deferred to project leadership for paper inclusion.
