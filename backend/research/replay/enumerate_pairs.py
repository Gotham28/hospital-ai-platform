"""Pair enumeration across development split using exact v5 context construction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Generator, NamedTuple

from backend.research.guard.nli import _decompose_passages, _select_candidate_passages
from backend.research.replay.cache import DEFAULT_MODEL_REVISION, make_key
from backend.research.run_guard_calibration import load_inputs, selected_items


class PairRecord(NamedTuple):
    answer_id: str
    claim_index: int
    passage_index: int
    passage: str
    claim: str
    key: str


def enumerate_development_pairs(
    traces_path: Path | str = "backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl",
    *,
    model_revision: str = DEFAULT_MODEL_REVISION,
) -> Generator[PairRecord, None, None]:
    """Rebuild context exactly as the v5 runner did (citing adapt_ragtruth / load_inputs)

    and emit the candidate (passage, claim) pairs selected by _select_candidate_passages.
    """
    manifest, responses = load_inputs()
    dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}

    traces_file = Path(traces_path)
    traces = [json.loads(line) for line in traces_file.read_text(encoding="utf-8").splitlines()]

    for trace in traces:
        tid = str(trace["id"])
        item = dev_items[tid]
        decomposed = _decompose_passages(item["context"])

        for c_idx, claim_dict in enumerate(trace["claims"]):
            claim_text = claim_dict["text"]
            active_passages = _select_candidate_passages(claim_text, decomposed, max_candidates=4)
            for p_idx, passage in enumerate(active_passages):
                key = make_key(passage, claim_text, model_revision)
                yield PairRecord(
                    answer_id=tid,
                    claim_index=c_idx,
                    passage_index=p_idx,
                    passage=passage,
                    claim=claim_text,
                    key=key,
                )


def main() -> None:
    print("Enumerating development pairs (exact v5 context + candidate selection)...")
    total_pairs = 0
    unique_keys = set()
    unique_pairs = set()

    for r in enumerate_development_pairs():
        total_pairs += 1
        unique_keys.add(r.key)
        unique_pairs.add((r.passage, r.claim))

    print(f"Total emitted candidate pairs: {total_pairs}")
    print(f"Unique (passage, claim) pairs: {len(unique_pairs)}")
    print(f"Unique sha256 cache keys     : {len(unique_keys)}")
    print(f"Duplicate pairs eliminated   : {total_pairs - len(unique_pairs)}")


if __name__ == "__main__":
    main()
