# G-03: Public Dataset and Baseline Shortlist

**Decision recorded:** 2026-10-07
**Scope:** standalone research evaluation only. The dataset is not used in the
AROGYA application or with patient text.

## Recommendation

Use the **RAGTruth QA test split** for the public evaluation and select a
**RARR-style attribution-and-revision baseline** for comparison.

RAGTruth is the closest fit because every QA item supplies a question, retrieved
passages, an instruction prompt, and a generated response with human
hallucination-span labels. Its repository is MIT licensed. G-04 will take a
fixed, seeded sample of 300 QA source items and will exclude responses marked
as truncated or otherwise unsuitable by the dataset.

The RARR baseline is the closest published post-generation method: it finds
support for claims, then revises unsupported text while preserving as much of
the response as possible. The original method uses web search and an LLM. For
this project, G-12 must use the passages already supplied by RAGTruth instead
of web search, and a local model rather than a paid API. That is an adaptation,
not a reproduction; `baseline_notes.md` must describe it precisely before any
comparison is reported.

## Candidate public datasets

| Dataset | Evidence and size | Licence | Conditions supported | Fit |
| --- | --- | --- | --- | --- |
| **RAGTruth** (selected) | 2,965 source items and 17,790 RAG-generated responses; the QA portion has 989 source items and 5,934 responses. Human labels identify hallucinated spans. | MIT | Correct retrieved data and naturally generated responses, including unsupported and contradictory content. It does not itself provide a controlled altered-context condition. | Directly evaluates grounding against retrieved passages and supports post-generation checking. |
| HaluEval | 35,000 hallucinated and normal samples across QA, dialogue, and summarisation. | MIT | Includes external-knowledge hallucination recognition; its main task is recognition rather than checking a fixed RAG context after generation. | Useful secondary detector benchmark, but weaker match for a context-bound grounding guard. |
| FaithDial | About 50,000 turns in 5.5K knowledge-grounded dialogues; faithful replies were edited from Wizard of Wikipedia responses. | Verify the release terms before use. | Faithful versus hallucinated dialogue turns with knowledge snippets; it does not target RAG answer post-processing. | Strong grounding resource, but dialogue framing differs from AROGYA question answering. |

Sources:

- RAGTruth paper: https://aclanthology.org/2024.acl-long.585/
- RAGTruth data and licence: https://github.com/ParticleMedia/RAGTruth
- HaluEval paper: https://aclanthology.org/2023.emnlp-main.397/
- HaluEval data and licence: https://github.com/RUCAIBox/HaluEval
- FaithDial paper: https://aclanthology.org/2022.tacl-1.84/

## Candidate baseline methods

| Method | What it needs | Cost per answer | Public implementation | Reproducibility and fit |
| --- | --- | --- | --- | --- |
| **RARR** (selected, adapted) | Claim research, attribution, and revision. The original uses an LLM and web search. | Original configuration has model and search cost. The planned adaptation uses the given RAG passages and a local model. | https://github.com/anthonywchen/RARR | Best conceptual match because it revises unsupported content after generation. The context-only adaptation must be disclosed. |
| SummaC | A local NLI-based source-consistency model; no training required for its released checkpoints. | Local inference only. | https://github.com/tingofurro/summac | Good lightweight detector baseline, but it scores consistency and does not repair an answer. It is a fallback if a local RARR revision model cannot be run reliably. |
| RAGAS Faithfulness | An LLM to split claims and judge each against retrieved context. | Depends on the selected evaluator model. | https://github.com/vibrantlabsai/ragas | Useful evaluation metric, but not a correction method. It should be used only as an auxiliary metric, not as the G-12 baseline. |

Sources:

- RARR paper: https://aclanthology.org/2023.acl-long.910/
- SummaC paper: https://aclanthology.org/2022.tacl-1.10/
- RAGAS faithfulness documentation: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/

## Decisions for the next tasks

1. G-04 will build a loader for the RAGTruth QA test data, select 300 source
   items with a documented fixed random seed, and support a pretend-model
   dry-run. It will not download or commit the dataset.
2. G-12 will implement the context-only local RARR adaptation behind the same
   interface as the grounding guard. The notes will list every difference from
   the published method.
3. No conclusions about which method is better may be made until G-13 and
   G-14 produce measured results.

## Limits already known

- RAGTruth is English-only, so it validates generality beyond hospital data but
  cannot validate Malayalam performance.
- The RAGTruth labels describe the original generated responses. Newly generated
  answers need separate scoring or human review.
- Substituting supplied passages for RARR's web-search stage changes the
  baseline. This is necessary to compare methods over the same evidence, and it
  must be stated in every report.
