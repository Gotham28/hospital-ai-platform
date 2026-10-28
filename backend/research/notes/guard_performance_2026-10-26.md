# Guard performance -- 2026-10-26

## Current-run measurements

Frozen synthetic fixtures; existing models, thresholds and guard behavior unchanged.
Holdout is primary. Tuning and all-100 results are descriptive, not independent tests.

| Partition | Answers | Gold claims | Claim accuracy | Macro F1 | Detection precision | Recall | F1 | False alterations | Fully intercepted / erroneous |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all/all | 100 | 114 | 0.658 | 0.648 | 0.692 | 1.000 | 0.818 | 24/46 | 53/54 |
| all/en | 50 | 58 | 0.897 | 0.877 | 0.875 | 1.000 | 0.933 | 4/22 | 28/28 |
| all/ml | 50 | 56 | 0.411 | 0.403 | 0.565 | 1.000 | 0.722 | 20/24 | 25/26 |
| tuning/all | 50 | 57 | 0.649 | 0.643 | 0.744 | 1.000 | 0.853 | 10/21 | 29/29 |
| tuning/en | 25 | 29 | 0.931 | 0.919 | 0.938 | 1.000 | 0.968 | 1/10 | 15/15 |
| tuning/ml | 25 | 28 | 0.357 | 0.351 | 0.609 | 1.000 | 0.757 | 9/11 | 14/14 |
| holdout/all | 50 | 57 | 0.667 | 0.652 | 0.641 | 1.000 | 0.781 | 14/25 | 24/25 |
| holdout/en | 25 | 29 | 0.862 | 0.835 | 0.812 | 1.000 | 0.897 | 3/12 | 13/13 |
| holdout/ml | 25 | 28 | 0.464 | 0.452 | 0.522 | 1.000 | 0.686 | 11/13 | 11/12 |

## Confusion matrices

Rows are gold; columns are supported, unsupported, contradicted, unmatched.

holdout/en
```json
{
  "supported": {
    "supported": 13,
    "unsupported": 3,
    "contradicted": 0,
    "unmatched": 0
  },
  "unsupported": {
    "supported": 0,
    "unsupported": 4,
    "contradicted": 1,
    "unmatched": 0
  },
  "contradicted": {
    "supported": 0,
    "unsupported": 0,
    "contradicted": 8,
    "unmatched": 0
  }
}
```

holdout/ml
```json
{
  "supported": {
    "supported": 3,
    "unsupported": 8,
    "contradicted": 5,
    "unmatched": 0
  },
  "unsupported": {
    "supported": 0,
    "unsupported": 3,
    "contradicted": 1,
    "unmatched": 0
  },
  "contradicted": {
    "supported": 0,
    "unsupported": 1,
    "contradicted": 7,
    "unmatched": 0
  }
}
```

all/en
```json
{
  "supported": {
    "supported": 25,
    "unsupported": 5,
    "contradicted": 0,
    "unmatched": 0
  },
  "unsupported": {
    "supported": 0,
    "unsupported": 9,
    "contradicted": 1,
    "unmatched": 0
  },
  "contradicted": {
    "supported": 0,
    "unsupported": 0,
    "contradicted": 18,
    "unmatched": 0
  }
}
```

all/ml
```json
{
  "supported": {
    "supported": 5,
    "unsupported": 13,
    "contradicted": 12,
    "unmatched": 0
  },
  "unsupported": {
    "supported": 0,
    "unsupported": 7,
    "contradicted": 2,
    "unmatched": 0
  },
  "contradicted": {
    "supported": 0,
    "unsupported": 6,
    "contradicted": 11,
    "unmatched": 0
  }
}
```

## English minus Malayalam gaps

```json
{
  "all": {
    "claim_accuracy": 0.48583743842364535,
    "claim_macro_f1": 0.4741800241800241,
    "detection_f1": 0.21111111111111114,
    "false_alteration_rate": -0.6515151515151516,
    "detection_precision": 0.3097826086956522,
    "detection_recall": 0.0,
    "detection_accuracy": 0.32000000000000006,
    "claim_supported_precision": 0.0,
    "claim_supported_recall": 0.6666666666666667,
    "claim_supported_f1": 0.6233766233766234,
    "claim_unsupported_precision": 0.3736263736263737,
    "claim_unsupported_recall": 0.12222222222222223,
    "claim_unsupported_f1": 0.35,
    "claim_contradicted_precision": 0.5073684210526315,
    "claim_contradicted_recall": 0.3529411764705882,
    "claim_contradicted_f1": 0.4491634491634492,
    "latency_mean_seconds": -3.1399649519999913,
    "latency_p50_seconds": -2.909633200000144,
    "latency_p95_seconds": -5.508482159999765
  },
  "tuning": {
    "claim_accuracy": 0.5738916256157636,
    "claim_macro_f1": 0.568135081292976,
    "detection_f1": 0.2109851787271142,
    "false_alteration_rate": -0.7181818181818183,
    "detection_precision": 0.3288043478260869,
    "detection_recall": 0.0,
    "detection_accuracy": 0.31999999999999995,
    "claim_supported_precision": 0.0,
    "claim_supported_recall": 0.7142857142857142,
    "claim_supported_f1": 0.6730769230769231,
    "claim_unsupported_precision": 0.4285714285714286,
    "claim_unsupported_recall": 0.19999999999999996,
    "claim_unsupported_f1": 0.412280701754386,
    "claim_contradicted_precision": 0.6666666666666667,
    "claim_contradicted_recall": 0.5555555555555556,
    "claim_contradicted_f1": 0.6190476190476191,
    "latency_mean_seconds": -3.2787705399999867,
    "latency_p50_seconds": -3.0710433999997804,
    "latency_p95_seconds": -4.93527508000052
  },
  "holdout": {
    "claim_accuracy": 0.397783251231527,
    "claim_macro_f1": 0.38231290701398535,
    "detection_f1": 0.21083743842364533,
    "false_alteration_rate": -0.5961538461538461,
    "detection_precision": 0.2907608695652174,
    "detection_recall": 0.0,
    "detection_accuracy": 0.31999999999999995,
    "claim_supported_precision": 0.0,
    "claim_supported_recall": 0.625,
    "claim_supported_f1": 0.5807622504537205,
    "claim_unsupported_precision": 0.3214285714285714,
    "claim_unsupported_recall": 0.050000000000000044,
    "claim_unsupported_f1": 0.29166666666666663,
    "claim_contradicted_precision": 0.3504273504273504,
    "claim_contradicted_recall": 0.125,
    "claim_contradicted_f1": 0.27450980392156865,
    "latency_mean_seconds": -3.0011593639999954,
    "latency_p50_seconds": -2.2389154000002236,
    "latency_p95_seconds": -5.520263339999929
  }
}
```

## Conflict evaluation (40 cases)

```json
{
  "all": {
    "presence": {
      "n": 40,
      "tp": 18,
      "fp": 5,
      "fn": 2,
      "tn": 15,
      "precision": 0.782608695652174,
      "recall": 0.9,
      "f1": 0.8372093023255814,
      "accuracy": 0.825
    },
    "type_set_exact_accuracy": 0.7,
    "per_type": {
      "instruction_vs_data": {
        "n": 40,
        "tp": 10,
        "fp": 6,
        "fn": 0,
        "tn": 24,
        "precision": 0.625,
        "recall": 1.0,
        "f1": 0.7692307692307693,
        "accuracy": 0.85
      },
      "answer_vs_data": {
        "n": 40,
        "tp": 8,
        "fp": 5,
        "fn": 2,
        "tn": 25,
        "precision": 0.6153846153846154,
        "recall": 0.8,
        "f1": 0.6956521739130435,
        "accuracy": 0.825
      },
      "answer_follows_instruction_against_data": {
        "n": 40,
        "tp": 8,
        "fp": 0,
        "fn": 2,
        "tn": 30,
        "precision": 1.0,
        "recall": 0.8,
        "f1": 0.8888888888888888,
        "accuracy": 0.95
      }
    }
  },
  "en": {
    "presence": {
      "n": 20,
      "tp": 10,
      "fp": 2,
      "fn": 0,
      "tn": 8,
      "precision": 0.8333333333333334,
      "recall": 1.0,
      "f1": 0.9090909090909091,
      "accuracy": 0.9
    },
    "type_set_exact_accuracy": 0.8,
    "per_type": {
      "instruction_vs_data": {
        "n": 20,
        "tp": 5,
        "fp": 4,
        "fn": 0,
        "tn": 11,
        "precision": 0.5555555555555556,
        "recall": 1.0,
        "f1": 0.7142857142857143,
        "accuracy": 0.8
      },
      "answer_vs_data": {
        "n": 20,
        "tp": 5,
        "fp": 0,
        "fn": 0,
        "tn": 15,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
        "accuracy": 1.0
      },
      "answer_follows_instruction_against_data": {
        "n": 20,
        "tp": 5,
        "fp": 0,
        "fn": 0,
        "tn": 15,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
        "accuracy": 1.0
      }
    }
  },
  "ml": {
    "presence": {
      "n": 20,
      "tp": 8,
      "fp": 3,
      "fn": 2,
      "tn": 7,
      "precision": 0.7272727272727273,
      "recall": 0.8,
      "f1": 0.7619047619047619,
      "accuracy": 0.75
    },
    "type_set_exact_accuracy": 0.6,
    "per_type": {
      "instruction_vs_data": {
        "n": 20,
        "tp": 5,
        "fp": 2,
        "fn": 0,
        "tn": 13,
        "precision": 0.7142857142857143,
        "recall": 1.0,
        "f1": 0.8333333333333334,
        "accuracy": 0.9
      },
      "answer_vs_data": {
        "n": 20,
        "tp": 3,
        "fp": 5,
        "fn": 2,
        "tn": 10,
        "precision": 0.375,
        "recall": 0.6,
        "f1": 0.46153846153846156,
        "accuracy": 0.65
      },
      "answer_follows_instruction_against_data": {
        "n": 20,
        "tp": 3,
        "fp": 0,
        "fn": 2,
        "tn": 15,
        "precision": 1.0,
        "recall": 0.6,
        "f1": 0.75,
        "accuracy": 0.9
      }
    }
  }
}
```

## Fact-lock target-status evaluation (40 cases)

```json
{
  "lang/all": {
    "n": 40,
    "correct": 40,
    "accuracy": 1.0
  },
  "lang/en": {
    "n": 20,
    "correct": 20,
    "accuracy": 1.0
  },
  "lang/ml": {
    "n": 20,
    "correct": 20,
    "accuracy": 1.0
  },
  "type/doctor_name": {
    "n": 8,
    "correct": 8,
    "accuracy": 1.0
  },
  "type/price": {
    "n": 10,
    "correct": 10,
    "accuracy": 1.0
  },
  "type/test_name": {
    "n": 6,
    "correct": 6,
    "accuracy": 1.0
  },
  "type/time": {
    "n": 8,
    "correct": 8,
    "accuracy": 1.0
  },
  "type/weekday": {
    "n": 8,
    "correct": 8,
    "accuracy": 1.0
  },
  "expected/changed": {
    "n": 16,
    "correct": 16,
    "accuracy": 1.0
  },
  "expected/survived": {
    "n": 20,
    "correct": 20,
    "accuracy": 1.0
  },
  "expected/unverified": {
    "n": 4,
    "correct": 4,
    "accuracy": 1.0
  }
}
```

## CPU latency

Cold imports/model load: 10.333 seconds.
Excluded warm-up (one answer in each language): 2.890 seconds.
Total evaluation wall time: 339.355 seconds.

| Warm guard answers | n | Mean seconds | p50 seconds | p95 seconds |
|---|---:|---:|---:|---:|
| all/all | 100 | 2.680 | 2.233 | 6.087 |
| all/en | 50 | 1.110 | 0.937 | 2.304 |
| all/ml | 50 | 4.250 | 3.846 | 7.812 |

## Case failures

All incorrect claim-verdict rows and original outputs are preserved in metrics.json/cases.jsonl.
```json
{
  "claim_verdict_cases": [
    7,
    18,
    27,
    28,
    29,
    31,
    32,
    33,
    34,
    35,
    36,
    40,
    41,
    42,
    44,
    45,
    46,
    47,
    49,
    50,
    51,
    54,
    55,
    70,
    76,
    77,
    79,
    80,
    82,
    84,
    86,
    88,
    90,
    92,
    94,
    95,
    98,
    99,
    100
  ],
  "false_alteration_ids": [
    7,
    31,
    32,
    33,
    36,
    41,
    45,
    47,
    49,
    50,
    51,
    54,
    70,
    76,
    80,
    82,
    84,
    86,
    88,
    90,
    92,
    94,
    98,
    100
  ],
  "residual_error_ids": [
    79
  ],
  "conflict_type_set_ids": [
    "en-07",
    "en-09",
    "en-15",
    "en-17",
    "ml-22",
    "ml-25",
    "ml-26",
    "ml-27",
    "ml-29",
    "ml-33",
    "ml-37",
    "ml-40"
  ],
  "fact_lock_ids": []
}
```

## Definitions and limitations

- Detection positive: any predicted unsupported/contradicted claim. Gold positive: unsupported/contradicted overall answer. Conflicts alone do not count as answer claim detection.
- Claim spans are aligned in original answer text. Complete contiguous fragments are grouped; contradiction takes precedence over unsupported, then supported. Missing/ambiguous claims count as unmatched errors, never disappear from the denominator.
- Full interception requires the declared replacements to reproduce final_answer and remove all original alphanumeric content of every erroneous gold claim. Partial removal is unresolved. Interception is redaction, not factual correction or acceptable patient wording.
- False alteration denominator is gold-supported answers. Unnecessary redaction can damage an otherwise correct answer.
- The old splitter recall suite accepts a substring such as Dr. as a full claim; its 100% does not establish complete extraction or verification accuracy. New metrics disclose fragment groups.
- Conflict presence and exact type sets are labelled; evidence correctness is not. Fact-lock evaluates only the labelled target type/status; extra types are ignored, and entity attribution/completeness is not gold-labelled.
- Fact-lock name aliases cover synthetic Test One--Ten names; they do not prove general transliteration. These 40 cases do not cover number/date targets.
- Frozen synthetic holdout is small and related to tuning data; no new real-world data, native-reader acceptance, clinical safety, production integration, concurrent-load or provider acceptance is established.
- Thresholds were not retuned. Undefined denominators are null in JSON/undefined here. Percentiles use linear interpolation. Socket connections and model downloads were blocked during inference.
- Full per-class precision/recall/F1, residual error counts, alignments and per-case results are in metrics.json/cases.jsonl alongside raw suite outputs and environment metadata.

## Focused guard follow-ups (not changed by this task)

- Abbreviation fragmentation is source-confirmed at guard/claims.py:7,65 and per-fragment redaction at guard/guard.py:95-110. Case 51 needlessly removes a supported prefix; case 79 leaves an unsupported doctor fragment despite changed=true. Add bilingual abbreviation regressions in a separate algorithm task.
- Malayalam false alterations also occur on whole single-fragment claims (for example cases 80 and 98). Eight of the 20 altered supported Malayalam answers involve fragmentation; twelve do not. Abbreviation repair alone cannot resolve the measured issue.
- guard/nli.py:17 omits English fee/cost/INR price cues from its exact-value parser, while guard/factlock.py has a different price parser. This is a source-level weakness. The current outputs do not retain pivot text or NLI scores, so do not attribute a particular measured failure to translation versus NLI without a dedicated diagnostic task.
- Fact locks are report-only at guard/guard.py:123-124. Cases 80/82/98 show survived values alongside redaction. Any arbitration policy between NLI and fact locks requires a separate decision; matching values alone do not prove a whole claim true.

## Runtime identity

```json
{
  "python": "3.11.6 (tags/v3.11.6:8b6ee5b, Oct  2 2023, 14:57:12) [MSC v.1935 64 bit (AMD64)]",
  "executable": "D:\\Hospital\\hospital-ai-platform\\backend\\research\\.venv\\Scripts\\python.exe",
  "platform": "Windows-10-10.0.26300-SP0",
  "processor": "Intel64 Family 6 Model 154 Stepping 3, GenuineIntel",
  "cpu_count": 12,
  "device": "cpu",
  "torch_threads": 4,
  "torch_interop_threads": 1,
  "packages": {
    "torch": "2.8.0+cpu",
    "transformers": "4.57.1",
    "huggingface-hub": "0.36.0",
    "sentencepiece": "0.2.1",
    "sacremoses": "0.1.1",
    "protobuf": "6.33.0",
    "numpy": "2.3.4"
  },
  "hashes": {
    "backend\\research\\fixtures\\guard_dev_set.json": "0d40008837d0ee91ef775b32f1b7bbaac4580dff980a252b9e548a53e94f71db",
    "backend\\research\\guard\\conflict_cases.jsonl": "34f8e05371480eb0b5fe6ad2ef689b115dae1790c9d2bff9958ddad0dea7bcec",
    "backend\\research\\guard\\factlock_cases.jsonl": "2049616edb9d5993cbf3f559928f44f4f9f02ec99845c4565ef7aeae0fc214e1",
    "backend\\research\\guard\\thresholds.json": "b212a0754a8017537c83f2a8c06c3f65fe95d9db277ef2d1fc3000030f32b78a"
  },
  "model_revisions": {
    "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli": "8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c",
    "Helsinki-NLP/opus-mt-ml-en": "ab043b0bded4c755ef79e30a8189085a17fe82ca"
  },
  "command": "D:\\Hospital\\hospital-ai-platform\\backend\\research\\.venv\\Scripts\\python.exe -B -u -m backend.research.run_guard_performance",
  "sockets_blocked": true,
  "offline": true
}
```
