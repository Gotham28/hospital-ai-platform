# English guard action-policy round, 2026-10-27

## Decision

**No action candidate was promoted.** All nine predeclared alternatives lowered
automatic alterations, but none reduced alterations by at least 20 percentage
points while retaining at least half of the baseline's complete interception
rate on development. The active English action policy remains `BASELINE`, and
Malayalam behavior is unchanged. The guard now exposes `altered` separately
from each English claim's detection `verdict`; this is research code only.

The full public benchmark completed before this round remains the guard's full
performance result. No new public-test benchmark is represented here as an
improvement. Its XNLI/IndicXNLI/RAGTruth test labels had already been inspected.

## Protocol and data boundary

- Pinned RAGTruth revision: `c103204b9ce28d6bbad859304bf30de72b8ed8fe`.
  Source and response SHA256 values, plus group IDs and counts, are in
  `../results/guard-action-policy-2026-10-27/development-manifest.json`.
- Only official RAGTruth train answers entered calibration. The train file
  contains 15,090 answers from 2,515 source groups; official train/test
  source IDs do not overlap. A seed-fixed source-group ranking selected 120
  development groups (720 answers) and 60 reserved validation groups (360
  answers), balanced across QA, Summary and Data2txt. The selected groups do
  not overlap. No published test labels selected a candidate.
- The development set has 399 answers without published error spans and 321
  with them. Validation has 207 and 153 respectively. No-span answers are
  treated as apparently clean for false-alteration measurement, although
  annotation may be incomplete.
- Frozen policies: baseline plus contradiction score minima 0.5/0.7/0.9
  crossed with neutral action off/0.8/0.95. For neutral-on policies,
  entailment must be at most 0.2; exact numeric-rule overrides never trigger
  candidate alteration. The complete grid and selection rule were saved
  before scoring. No parameter was changed after seeing development outcomes.
- Per-claim verdict, score vector and exact-rule provenance were cached once
  per answer and replayed across the candidate grid. Development inference
  completed 720/720 answers; validation completed 360/360, with no duplicate
  IDs or inference failures. Validation scored baseline only because no
  development candidate qualified.

## Outcomes

Detection means an `unsupported` or `contradicted` verdict. Alteration means
text was actually replaced by `[FLAG_TEXT]`. Complete interception requires
the altered character mask to cover every published error character in an
answer. It does not mean a corrected, readable answer was produced.

| Split/policy | False alterations / no-span answers | Complete interceptions / erroneous answers | Residual erroneous answers | Character precision / recall |
|---|---:|---:|---:|---:|
| Development baseline | 395/399 (99.0%) | 259/321 (80.7%) | 62 | 5.82% / 96.92% |
| Development 0.5 contradiction, 0.8 neutral | 347/399 (87.0%) | 134/321 (41.7%) | 187 | 7.07% / 67.85% |
| Development 0.9 contradiction, neutral off | 36/399 (9.0%) | 0/321 (0%) | 321 | 4.45% / 1.19% |
| Reserved validation baseline | 205/207 (99.0%) | 130/153 (85.0%) | 23 | 5.91% / 96.91% |

The 0.5/0.8 policy kept 51.7% of baseline complete interception but reduced
false alterations by only 12.0 percentage points. The stricter 0.9/off policy
barely altered clean answers but intercepted none of the 321 erroneous
development answers completely. None met both gates. Detection verdicts were
held fixed in policy replay: development TP 321/321 and FP 395/399, and
validation TP 153/153 and FP 205/207. These high apparent detection rates
therefore also reflect near-universal positive predictions.

Source-group percentile bootstrap, 2,000 samples: development baseline
false-alteration rate 95% interval 97.89–99.76%, complete-interception rate
75.00–85.71%; validation baseline 97.52–100.00% and 76.82–91.30%.
Development baseline changed 716/720 answers; validation changed 358/360.
V3 calibration claim-check inference latency on the GPU was 0.54 seconds mean,
0.47 seconds median and 1.07 seconds p95 on validation (n=360). This latency
excludes conflict surfacing, fact lock and the later token audit; use the
original full benchmark for assembled-guard latency.

The frozen 512-token NLI limit was exceeded for 4,342/6,427 (67.6%)
development claim/evidence pairs and 1,965/3,232 (60.8%) validation pairs;
the longest untruncated pair was 2,806 tokens in development. This is a
plausible contributor to poor RAGTruth specificity, not a proved causal
attribution. Context chunking and model changes are outside this task.

## Existing full public-test performance (no new candidate run)

The earlier full CUDA evaluation has 22,740/22,740 completed conditions and
zero failures. It reports English XNLI guard detection F1 92.14%, with
510/1,670 supported answers altered (30.54%); Malayalam F1 84.08%, with
1,203/1,670 altered (72.04%). For 2,700 RAGTruth test answers, detection F1
was 52.07%, 1,733/1,757 no-span answers were altered (98.63%), 814/943
annotated-error answers were fully intercepted, and redacted-character
precision was 4.34%. Mean assembled-guard latency was 0.037 s for English
XNLI, 0.435 s for Malayalam XNLI and 2.111 s for RAGTruth; RAGTruth had
40,826 truncated NLI pairs. See the original `full-cuda/metrics.json` and
`guard_external_performance_2026-10-26.md` for complete denominators,
uncertainty and caveats. These general-domain datasets make no clinical-safety
claim.

## Evidence and limits

The raw split, trace, selection, validation, token audit and metric files are
under `../results/guard-action-policy-2026-10-27/`. The original inference
terminal transcript was not retained, and its original trace identity did not
cover the full producer code. Those historical traces are preserved as legacy
evidence; a versioned rerun records complete command output and a stronger
identity. The v2 rerun completed all 720/360 answers with captured commands,
stdout/stderr and exit codes, but review found that its identity omitted
`guard.py`, a live scoring and threshold-loader dependency. V2 remains
historical evidence; a v3 rerun binds that dependency and the other local
producer modules, pinned model revisions, library versions, device and
precision. Its identity is checked before resume, replay, token audit and
verification. The negative selection and baseline validation counts remain
unchanged. Source-group intervals
describe sample variation under this grouped resampling, not all deployment
uncertainty. Calibration traces contain public answer/claim text; keep them
local and out of security logs. Exact commands and verification output are in
the task HANDOFF. An actual CUDA smoke on the first published XNLI/IndicXNLI
pair (`pairID` 4) reproduced the saved assembled-guard result exactly in
English and Malayalam after omitting the new English `altered` display field.
Prior test labels were already inspected, so any later
public-test comparison is exploratory. Further improvement should address
long-context evidence and claim-level truth labels in a separately scoped
round, with an independent final holdout.
