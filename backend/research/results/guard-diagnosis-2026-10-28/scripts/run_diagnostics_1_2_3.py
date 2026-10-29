import sys
import json
import random
import time
from pathlib import Path
import torch

sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from backend.research.guard.nli import MultilingualNLIScorer, _decompose_passages, _select_candidate_passages
from backend.research.replay.cache import NLICache, make_key
from backend.research.run_guard_calibration import load_inputs, selected_items

torch.set_num_threads(4)
print(f"PyTorch version: {torch.__version__}, Threads: {torch.get_num_threads()}")

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

census_path = Path("C:/Users/Sreehari/.gemini/antigravity-ide/brain/d3e4acec-ffb6-4824-b295-0bcf398df4e3/scratch/census_results.json")
census_data = json.loads(census_path.read_text(encoding="utf-8"))
claims_45 = census_data["claims_above_1e4"]

print(f"Loaded {len(claims_45)} claims with score difference > 1e-4.")

# Initialize scorer on CPU exactly as v5 runner does (batch_size=8)
scorer = MultilingualNLIScorer(device="cpu", batch_size=8)

# =========================================================================
# TASK 1: Live vs Cache vs Stored for the 45 claims
# =========================================================================
print("\n" + "=" * 70)
print("TASK 1: LIVE VS CACHE VS STORED (45 CLAIMS)")
print("=" * 70)

tol = 1e-4
results_45 = []
table_specific = {}

live_matches_stored_count = 0
live_matches_cache_count = 0
neither_count = 0

for idx, c_info in enumerate(claims_45, 1):
    aid = c_info["answer_id"]
    cidx = c_info["claim_index"]
    item = dev_items[aid]
    stored_claim = stored_by_id[aid]["claims"][cidx]
    claim_text = stored_claim["text"]
    passages = _decompose_passages(item["context"])
    candidates = _select_candidate_passages(claim_text, passages, max_candidates=4)
    
    # Live score: exactly as v5 path does (all candidate passages of this claim in a single call)
    pairs = [(p, claim_text) for p in candidates]
    live_scores = scorer.score_pairs(pairs)
    
    # Best live score selection (exact v5 formula)
    best_live_idx = max(range(len(live_scores)), key=lambda i: max(live_scores[i].entailment, live_scores[i].contradiction))
    best_live = live_scores[best_live_idx]
    
    # Cache scores for candidates
    cache_scores = []
    for p in candidates:
        k = make_key(p, claim_text)
        cs = cache.get(k)
        assert cs is not None, f"Missing cache key for {aid} claim {cidx}"
        cache_scores.append(cs)
        
    best_cache_idx = max(range(len(cache_scores)), key=lambda i: max(cache_scores[i].entailment, cache_scores[i].contradiction))
    best_cache = cache_scores[best_cache_idx]
    
    # Stored scores
    stored_s = stored_claim["scores"]
    
    # Compare best_live vs stored
    diff_live_stored = max(abs(best_live.entailment - stored_s["entailment"]),
                           abs(best_live.neutral - stored_s["neutral"]),
                           abs(best_live.contradiction - stored_s["contradiction"]))
    
    # Compare best_live vs best_cache
    diff_live_cache = max(abs(best_live.entailment - best_cache.entailment),
                          abs(best_live.neutral - best_cache.neutral),
                          abs(best_live.contradiction - best_cache.contradiction))
    
    match_stored = (diff_live_stored <= tol)
    match_cache = (diff_live_cache <= tol)
    
    if match_cache:
        live_matches_cache_count += 1
    elif match_stored:
        live_matches_stored_count += 1
    else:
        neither_count += 1
        
    status = "MATCH_CACHE" if match_cache else ("MATCH_STORED" if match_stored else "NEITHER")
    
    results_45.append({
        "answer_id": aid,
        "claim_index": cidx,
        "claim_text": claim_text,
        "status": status,
        "diff_live_stored": diff_live_stored,
        "diff_live_cache": diff_live_cache,
        "best_live_idx": best_live_idx,
        "best_cache_idx": best_cache_idx,
    })
    
    # Save candidate-level table for 12426 claims 2, 4 and 12429 claims 3, 5
    if (aid == "12426" and cidx in (2, 4)) or (aid == "12429" and cidx in (3, 5)):
        table_specific[f"{aid}_{cidx}"] = {
            "answer_id": aid,
            "claim_index": cidx,
            "claim_text": claim_text,
            "stored_winning_scores": stored_s,
            "candidates": [
                {
                    "cand_idx": i,
                    "passage_snippet": p[:90] + "...",
                    "live": vars(live_scores[i]),
                    "cache": vars(cache_scores[i]),
                }
                for i, p in enumerate(candidates)
            ]
        }

print(f"\nTask 1 Summary over 45 claims:")
print(f"  Live matches Cache (<= 1e-4) : {live_matches_cache_count} / 45")
print(f"  Live matches Stored (<= 1e-4): {live_matches_stored_count} / 45")
print(f"  Neither                      : {neither_count} / 45")

# Print detailed status for each of the 45 claims
print("\nDetailed breakdown of 45 claims:")
for r in results_45:
    print(f"Answer {r['answer_id']:>5} claim {r['claim_index']:>2}: status={r['status']} | diff(live, cache)={r['diff_live_cache']:.6f} | diff(live, stored)={r['diff_live_stored']:.6f}")

# Print full table for 12426 claims 2 & 4 and 12429 claims 3 & 5
print("\n" + "=" * 70)
print("FULL CANDIDATE PASSAGE TABLE FOR 12426 (claims 2, 4) AND 12429 (claims 3, 5)")
print("=" * 70)
for k, t in table_specific.items():
    print(f"\nTarget: Answer {t['answer_id']} Claim {t['claim_index']}")
    print(f"Claim: {repr(t['claim_text'])}")
    print(f"Stored trace winning scores: E={t['stored_winning_scores']['entailment']:.6f}, N={t['stored_winning_scores']['neutral']:.6f}, C={t['stored_winning_scores']['contradiction']:.6f}")
    print("Candidate Passages:")
    for c in t["candidates"]:
        print(f"  [Cand {c['cand_idx']}] {c['passage_snippet']}")
        print(f"    Live:  E={c['live']['entailment']:.6f}, N={c['live']['neutral']:.6f}, C={c['live']['contradiction']:.6f}")
        print(f"    Cache: E={c['cache']['entailment']:.6f}, N={c['cache']['neutral']:.6f}, C={c['cache']['contradiction']:.6f}")


# =========================================================================
# TASK 2: Batch Sensitivity for 12426 claims 2 and 4
# =========================================================================
print("\n" + "=" * 70)
print("TASK 2: BATCH SENSITIVITY TEST (12426 CLAIMS 2 AND 4)")
print("=" * 70)

# 3 ways:
# Way A: batch size 1 (score each pair individually)
# Way B: one call of 3 (the 3 candidate pairs together)
# Way C: inside a batch of 16 padded with unrelated pairs

# Let's get 13 unrelated pairs from another answer to pad to 16
other_item = dev_items["10261"]
other_passages = _decompose_passages(other_item["context"])
unrelated_pairs = []
for p in other_passages:
    for c in stored_by_id["10261"]["claims"]:
        unrelated_pairs.append((p, c["text"]))
        if len(unrelated_pairs) >= 13:
            break
    if len(unrelated_pairs) >= 13:
        break

for cidx in [2, 4]:
    claim_text = stored_by_id["12426"]["claims"][cidx]["text"]
    cands = _select_candidate_passages(claim_text, _decompose_passages(dev_items["12426"]["context"]), max_candidates=4)
    target_pairs = [(p, claim_text) for p in cands]
    
    # Way A: batch size 1
    scorer_b1 = MultilingualNLIScorer(device="cpu", batch_size=1)
    scores_way_a = scorer_b1.score_pairs(target_pairs)
    
    # Way B: one call of 3 (batch_size >= 3)
    scorer_b3 = MultilingualNLIScorer(device="cpu", batch_size=8)
    scores_way_b = scorer_b3.score_pairs(target_pairs)
    
    # Way C: inside batch of 16 padded with 13 unrelated pairs
    padded_batch = target_pairs + unrelated_pairs[:13]
    scorer_b16 = MultilingualNLIScorer(device="cpu", batch_size=16)
    scores_padded = scorer_b16.score_pairs(padded_batch)
    scores_way_c = scores_padded[:len(target_pairs)]
    
    print(f"\n--- Claim {cidx}: {repr(claim_text)} ---")
    max_diff_across_ways = 0.0
    for pi in range(len(target_pairs)):
        sa = scores_way_a[pi]
        sb = scores_way_b[pi]
        sc = scores_way_c[pi]
        
        diff_ab = max(abs(sa.entailment - sb.entailment), abs(sa.neutral - sb.neutral), abs(sa.contradiction - sb.contradiction))
        diff_bc = max(abs(sb.entailment - sc.entailment), abs(sb.neutral - sc.neutral), abs(sb.contradiction - sc.contradiction))
        diff_ac = max(abs(sa.entailment - sc.entailment), abs(sa.neutral - sc.neutral), abs(sa.contradiction - sc.contradiction))
        max_pair_diff = max(diff_ab, diff_bc, diff_ac)
        if max_pair_diff > max_diff_across_ways:
            max_diff_across_ways = max_pair_diff
            
        print(f"Passage {pi}:")
        print(f"  Way A (bs=1)  : E={sa.entailment:.6f}, N={sa.neutral:.6f}, C={sa.contradiction:.6f}")
        print(f"  Way B (call=3): E={sb.entailment:.6f}, N={sb.neutral:.6f}, C={sb.contradiction:.6f}")
        print(f"  Way C (bs=16) : E={sc.entailment:.6f}, N={sc.neutral:.6f}, C={sc.contradiction:.6f}")
        print(f"  Max diff between ways for pair {pi}: {max_pair_diff:.8f}")
        
    print(f"Max difference across all ways for Claim {cidx}: {max_diff_across_ways:.8f}")


# =========================================================================
# TASK 3: Control on 100 random claims NOT in the 45 (seed 20261028)
# =========================================================================
print("\n" + "=" * 70)
print("TASK 3: CONTROL TEST (100 RANDOM CLAIMS NOT IN 45, SEED 20261028)")
print("=" * 70)

# Build list of all claims not in 45
claims_45_keys = {(c["answer_id"], c["claim_index"]) for c in claims_45}
all_eligible_claims = []
for aid, item in dev_items.items():
    stored = stored_by_id[aid]
    for cidx, c in enumerate(stored["claims"]):
        if (aid, cidx) not in claims_45_keys:
            all_eligible_claims.append((aid, cidx))

print(f"Total eligible claims not in 45: {len(all_eligible_claims)}")

random.seed(20261028)
sampled_100 = random.sample(all_eligible_claims, 100)

control_match_stored = 0
control_match_cache = 0
control_neither = 0

control_results = []
for aid, cidx in sampled_100:
    item = dev_items[aid]
    stored_c = stored_by_id[aid]["claims"][cidx]
    claim_text = stored_c["text"]
    passages = _decompose_passages(item["context"])
    candidates = _select_candidate_passages(claim_text, passages, max_candidates=4)
    
    pairs = [(p, claim_text) for p in candidates]
    live_scores = scorer.score_pairs(pairs)
    best_live_idx = max(range(len(live_scores)), key=lambda i: max(live_scores[i].entailment, live_scores[i].contradiction))
    best_live = live_scores[best_live_idx]
    
    cache_scores = [cache.get(make_key(p, claim_text)) for p in candidates]
    best_cache_idx = max(range(len(cache_scores)), key=lambda i: max(cache_scores[i].entailment, cache_scores[i].contradiction))
    best_cache = cache_scores[best_cache_idx]
    
    stored_s = stored_c["scores"]
    
    diff_live_stored = max(abs(best_live.entailment - stored_s["entailment"]),
                           abs(best_live.neutral - stored_s["neutral"]),
                           abs(best_live.contradiction - stored_s["contradiction"]))
    
    diff_live_cache = max(abs(best_live.entailment - best_cache.entailment),
                          abs(best_live.neutral - best_cache.neutral),
                          abs(best_live.contradiction - best_cache.contradiction))
    
    m_stored = (diff_live_stored <= tol)
    m_cache = (diff_live_cache <= tol)
    
    if m_stored:
        control_match_stored += 1
    if m_cache:
        control_match_cache += 1
    if not m_stored and not m_cache:
        control_neither += 1
        
    control_results.append({
        "answer_id": aid,
        "claim_index": cidx,
        "diff_live_stored": diff_live_stored,
        "diff_live_cache": diff_live_cache,
    })

print(f"\nControl 100 claims results:")
print(f"  Live matches Stored (<= 1e-4): {control_match_stored} / 100")
print(f"  Live matches Cache (<= 1e-4) : {control_match_cache} / 100")
print(f"  Neither                      : {control_neither} / 100")

# Save structured summary
out_path = Path("C:/Users/Sreehari/.gemini/antigravity-ide/brain/d3e4acec-ffb6-4824-b295-0bcf398df4e3/scratch/diagnostic_results.json")
out_path.write_text(json.dumps({
    "task1": {
        "live_matches_cache": live_matches_cache_count,
        "live_matches_stored": live_matches_stored_count,
        "neither": neither_count,
        "results": results_45,
        "tables": table_specific,
    },
    "task3": {
        "match_stored": control_match_stored,
        "match_cache": control_match_cache,
        "neither": control_neither,
    }
}, indent=2), encoding="utf-8")
print(f"\nStructured output saved to {out_path}")
