import json
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

from backend.research.guard.nli import _decompose_passages, _select_candidate_passages
from backend.research.replay.cache import NLICache, make_key
from backend.research.run_guard_calibration import load_inputs, selected_items

manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}
item_12426 = dev_items["12426"]
stored_traces = [json.loads(line) for line in Path("backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl").read_text(encoding="utf-8").splitlines()]
stored_12426 = [t for t in stored_traces if str(t["id"]) == "12426"][0]

cache = NLICache("backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl")

print("Task:", item_12426["task"])
print("Answer:", repr(item_12426["answer"]))
decomposed = _decompose_passages(item_12426["context"])
print("Decomposed passages count:", len(decomposed))

for idx in [2, 4]:
    c = stored_12426["claims"][idx]
    print(f"\n--- Claim {idx}: {repr(c['text'])} ---")
    print(f"Stored verdict: {c['verdict']}, exact: {c['exact_verdict']}")
    print(f"Stored scores: {c['scores']}")
    cands = _select_candidate_passages(c["text"], decomposed, max_candidates=4)
    print(f"Candidates count: {len(cands)}")
    for p_idx, p in enumerate(cands):
        k = make_key(p, c["text"])
        sc = cache.get(k)
        print(f"  Cand {p_idx} (len {len(p)}): key={k[:12]}")
        print(f"    Passage text snippet: {repr(p[:80])}")
        if sc:
            print(f"    Scores in cache: E={sc.entailment:.4f}, N={sc.neutral:.4f}, C={sc.contradiction:.4f}")
        else:
            print("    NOT IN CACHE!")
