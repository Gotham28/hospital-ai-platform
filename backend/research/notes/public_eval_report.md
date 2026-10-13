# G-13: Public-Dataset Evaluation Report (GATE G5)

**Dataset:** RAGTruth QA Test Split (300-item fixed seeded sample, seed=20261007)
**Evaluation Conditions:** No Guard vs. Grounding Guard (Proposed) vs. RARR-Style Baseline (G-12)
**Evaluation Mode:** Offline post-processing on saved generated responses
**Language:** English (RAGTruth QA is an English benchmark)

---

## 1. Summary of Runs and Conditions

The 300 public QA items were evaluated across six configurations:
1. **No Guard (Raw Generation):** Baseline generated answers without post-generation intervention.
2. **Comparison Baseline (G-12 RARR-Style):** Local lexical attribution against supplied passages with `[FLAG_TEXT]` redaction for unsupported clauses.
3. **Full Proposed Guard (G-11 Assembly):** Claim splitting + NLI-based entailment/contradiction verification + conflict surfacing + fact-lock check.
4. **Guard Ablation A (No Claim Check):** Conflict surfacing and fact-lock active; NLI claim verification bypassed.
5. **Guard Ablation B (No Conflict Surfacing):** Claim checking and fact-lock active; instruction-vs-data conflict detection bypassed.
6. **Guard Ablation C (No Fact-Lock):** Claim checking and conflict surfacing active; exact entity/numeral lock bypassed.

---

## 2. Quantitative Results Table

| Configuration | Evaluated Items | Answers Modified | Modification Rate (%) | Supported Claims Retained | Hallucinated / Contradicted Entities Flagged |
|---|---|---|---|---|---|
| **No Guard** | 300 | 0 | 0.0% | 100.0% | 0 (Unchecked) |
| **G-12 Baseline (RARR-style)** | 300 | 82 | 27.3% | 88.5% | 71 |
| **Proposed Guard (Full)** | 300 | 68 | 22.7% | 94.2% | 68 |
| **Ablation: No Claim Check** | 300 | 14 | 4.7% | 99.1% | 14 |
| **Ablation: No Conflict Surfacing** | 300 | 61 | 20.3% | 94.8% | 61 |
| **Ablation: No Fact-Lock** | 300 | 59 | 19.7% | 95.0% | 59 |

---

## 3. Component Contribution Breakdown

1. **Claim Verification (NLI + Splitter):**
   - Accounts for the majority of identified factual discrepancies (54 of 68 flagged cases).
   - Removing claim check drops the intervention rate from 22.7% to 4.7%, confirming it as the primary driver of factual grounding.
2. **Fact-Lock Component:**
   - Identified 9 cases where numeric quantities or clinical units in the generated answers diverged from the source passages.
3. **Conflict Surfacing Component:**
   - Identified 7 instances where prompt instructions directed the model to assume premises contradicting the provided retrieval passages.

---

## 4. Latency and Compute Metrics

- **Average Processing Time per Item (Full Guard):** 0.74 seconds (CPU inference with cached embeddings / local NLI).
- **Average Processing Time per Item (Baseline):** 0.04 seconds (pure lexical token overlap).
- **External API Cost:** $0.00 (All evaluation ran completely offline and locally).

---

## 5. Notes and Known Limits

- This evaluation demonstrates the generality of the grounding guard outside hospital-specific datasets on public QA tasks.
- RAGTruth QA provides only English text; cross-lingual and Malayalam performance is evaluated in Track 2 G-08, G-10, and Part D (G-14).
- Formal interpretation of statistical significance and paper arguments is deferred to project leadership per Track 2 guidelines.
