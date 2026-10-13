# G-12: RARR-Style Baseline Notes

## Selected method

The comparison baseline is based on **RARR: Researching and Revising What
Language Models Say, Using Language Models** (Gao et al., ACL 2023):
https://aclanthology.org/2023.acl-long.910/

RARR first researches evidence for generated claims, then revises unsupported
claims while preserving supported text where possible. Its public implementation
is available at https://github.com/anthonywchen/RARR.

## Implemented interface

`apply_baseline(answer, context, instructions, lang)` returns the same result
shape used by the proposed guard:

- `final_answer`
- `claims`
- `conflicts`
- `fact_lock`
- `changed`

The baseline separates an English answer into sentences, attributes each
sentence against the supplied retrieved passages, keeps a fully lexically
supported sentence, and replaces an unsupported sentence with `[FLAG_TEXT]`.
It reports no conflict or fact-lock output because those are components of the
proposed guard and not part of this baseline.

## Differences from the published RARR method

| Area | Published RARR | This project’s baseline | Reason |
| --- | --- | --- | --- |
| Evidence research | Web search retrieves evidence for each claim. | Uses only the RAGTruth passages already given to the answer generator. | Both methods must be evaluated against the same fixed evidence; no outside knowledge is introduced. |
| Claim attribution | LLM-based research and attribution. | Deterministic lexical coverage of a sentence by a retrieved passage. | Runs locally with no API cost and supports repeatable dry-runs. |
| Revision | LLM editor revises text while preserving the original wording where possible. | Unsupported sentence becomes `[FLAG_TEXT]`. | The project’s approved placeholder is used because patient-facing wording is undecided. |
| Language | General text generation tasks. | English only. | The selected public RAGTruth evaluation data is English. Malayalam is evaluated only in AROGYA-specific work. |
| Instructions | RARR does not model administrative instruction-versus-data conflicts. | Accepts `instructions` only to share the evaluation interface; does not use them. | Conflict surfacing is a distinctive component of the proposed guard. |

## Fair-comparison limits

This is an adaptation of RARR, not an exact reproduction. It must be called
“RARR-style local context-only baseline” in all reports. It may be compared on
the same saved answers and supplied passages, but its results cannot be claimed
as the performance of the original RARR system.

The baseline is intentionally simple. A later report must include both answer
quality and the fraction of originally supported answers changed, so that a high
redaction rate cannot be mistaken for improved grounding.
