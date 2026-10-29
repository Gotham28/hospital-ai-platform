import sys
import json
from pathlib import Path
import torch

sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from backend.research.guard.nli import MultilingualNLIScorer, _decompose_passages, _select_candidate_passages
from backend.research.replay.cache import NLICache, make_key
from backend.research.run_guard_calibration import load_inputs, selected_items

print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"Default num threads: {torch.get_num_threads()}")

torch.set_num_threads(4)
print(f"Configured num threads: {torch.get_num_threads()}")

cache_path = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl"
cache = NLICache(cache_path)

manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}

traces_path = repo_root / "backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl"
stored_by_id = {}
with open(traces_path, "r", encoding="utf-8") as f:
    for line in f:
        row = json.loads(line)
        stored_by_id[str(row["id"])] = row

scorer = MultilingualNLIScorer(device="cpu", batch_size=8)

# Test 12426 claim 2 and 4
item_12426 = dev_items["12426"]
passages = _decompose_passages(item_12426["context"])

for cidx in [2, 4]:
    stored_c = stored_by_id["12426"]["claims"][cidx]
    claim_text = stored_c["text"]
    cands = _select_candidate_passages(claim_text, passages, max_candidates=4)
    print(f"\n==========================================")
    print(f"Testing 12426 claim {cidx}: {claim_text}")
    print(f"Stored scores: {stored_c['scores']}")
    
    # Live score in a single call of all candidate passages (as v5 does)
    pairs = [(p, claim_text) for p in cands]
    live_scores = scorer.score_pairs(pairs)
    
    for i, (p, live_s) in enumerate(zip(cands, live_scores)):
        k = make_key(p, claim_text)
        cache_s = cache.get(k)
        print(f"\nCandidate {i}:")
        print(f"  Live:   E={live_s.entailment:.6f}, N={live_s.neutral:.6f}, C={live_s.contradiction:.6f}")
        print(f"  Cache:  E={cache_s.entailment:.6f}, N={cache_s.neutral:.6f}, C={cache_s.contradiction:.6f}")
        diff_live_cache = max(abs(live_s.entailment - cache_s.entailment),
                              abs(live_s.neutral - cache_s.neutral),
                              abs(live_s.contradiction - cache_s.contradiction))
        print(f"  Diff(Live, Cache): {diff_live_cache:.6f}")
