# External guard performance: diagnosis (2026-10-26)

## Run integrity

The full CUDA run completed **22,740/22,740 expected unique outcomes**, with **0 failures**, in **8,258.492 seconds**. Source and data hashes match the frozen run manifest. The benchmark measures agreement with annotated outcomes and guard interventions; it does not establish factual correctness beyond those annotations.

| Evaluator | Precision | Recall | F1 | Mean latency |
|---|---:|---:|---:|---:|
| English raw NLI | 93.2% | 96.3% | 0.947 | 17.7 ms |
| English guarded NLI | 86.6% | 98.5% | 0.921 | 37.0 ms |
| ML raw NLI | 88.3% | 88.2% | 0.883 | 17.8 ms |
| ML guarded NLI | 73.3% | 98.7% | 0.841 | 435 ms |
| RAGTruth English guard | 35.2% | 99.9% | 0.521 | 2.11 s |

Guard false positives: English 510/1,670; ML 1,203/1,670; RAGTruth 1,733/1,757.

## Diagnosis

- Frozen thresholds (0.90/0.30) reproduce all **1,631** English clean, unchanged-single-claim outcomes without numeric overrides. **251** raw-correct cases become guard errors: **49.2%** of English guard false positives.
- ML guard preserves **467/1,670** supported outcomes and creates 870 false positives from raw-correct outcomes; 57 cases recover. Only 66/1,203 false positives are fragmented claims. The original full-run records lack translated claims and model scores, so native raw ML versus pivot-translation guard is not a controlled ablation. The new 12-case trace records translations, scores, and exact verdicts, including cases 8 and 14; because those cases were purposively selected, full ML causal attribution remains unresolved.
- Among RAGTruth cases without truncation, **672/693** are false positives. Numeric rules trigger claim flags across 243 clean responses (261 flagged claims); each response also has other flags. Removing numeric-only flags therefore clears zero whole responses with other verdicts frozen.
- Reviewed failures demonstrate colon overmatching, unnormalized `11:0` versus `11:00` times, and sentence splitting at `Batman v.`. Each RAG answer has one intact context, so cross-passage competition is not demonstrated as a cause.
- Metrics subgroup accounting omits 1,090 false-positive refusal characters and 401 truncated cases from their respective all-clean subgroup; overall counts include them. The classification helper silently zips unequal arrays, but present arrays are equal length.
- Official XNLI supplies one identical text pair with conflicting labels (4,357 versus 4,358). Threshold tuning used 28 ML and 29 English synthetic claims across 169 threshold pairs; ML pivot use was hardcoded despite a lower synthetic tuning score.

## Limits and next work

Primary aggregate metrics are valid. Source-cluster confidence intervals are recorded in `metrics.json`. Do not tune on inspected test labels. Next: trace and calibrate on independent source-grouped development data, fix numeric normalization and sentence splitting, then investigate long-context handling. No performance improvement is claimed; algorithms were unchanged.

The bounded 12-case illustrative replay is diagnostic only, not a population estimate. It completed; all 12 replay result objects exactly match the saved outcomes. Its added trace fields support case-level diagnosis, but not representative ML causal estimates.
