# G-08 NLI evaluation

Model: [MoritzLaurer/mDeBERTa-v3-base-mnli-xnli](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli)
Malayalam-to-English pivot: [Helsinki-NLP/opus-mt-ml-en](https://huggingface.co/Helsinki-NLP/opus-mt-ml-en)
Device: cpu
Thresholds were selected using tuning rows only; holdout labels were not used for tuning.
The pivot option translates Malayalam claims to English; context passages remain unchanged.
Exact-value overrides use nearby price, time, and duration keywords and may miss entity attribution.

Evaluation elapsed seconds: 62.46

| Option | Language | Entailment threshold | Contradiction threshold | Class | Precision | Recall |
|---|---|---:|---:|---|---:|---:|
| direct | en | 0.90 | 0.30 | unsupported | 1.000 | 0.800 |
| direct | en | 0.90 | 0.30 | contradicted | 0.889 | 1.000 |
| direct | ml | 0.85 | 0.75 | unsupported | 0.273 | 0.750 |
| direct | ml | 0.85 | 0.75 | contradicted | 0.714 | 0.625 |
| pivot | en | 0.90 | 0.30 | unsupported | 1.000 | 0.800 |
| pivot | en | 0.90 | 0.30 | contradicted | 0.889 | 1.000 |
| pivot | ml | 0.90 | 0.40 | unsupported | 0.273 | 0.750 |
| pivot | ml | 0.90 | 0.40 | contradicted | 0.538 | 0.875 |

The holdout report is a single evaluation. Do not adjust thresholds from these results.
