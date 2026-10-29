import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from backend.research.guard.claims import split_claims
from backend.research.guard.nli import ClaimAssessment, _decompose_passages, _select_candidate_passages, _typed_values
from backend.research.guard.action_policy import BASELINE, should_alter
from backend.research.guard.eval_external import removal_mask
from backend.research.guard import guard
from backend.research.replay.cache import NLICache, make_key
from backend.research.run_guard_calibration import load_inputs, selected_items, score_policy, metrics

cache_path = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl"
cache = NLICache(cache_path)
manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}

traces_path = repo_root / "backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl"
stored_traces = [json.loads(line) for line in traces_path.read_text(encoding="utf-8").splitlines()]
stored_by_id = {str(t["id"]): t for t in stored_traces}

rag_response_path = repo_root / "backend/research/results/guard-external-2026-10-26/data/rag-response.jsonl"
rag_labels_by_id = {}
with open(rag_response_path, "r", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("labels"):
            rag_labels_by_id[str(r["id"])] = r["labels"]

cthresh = 0.50

all_groups = sorted({item["group"] for item in dev_items.values()})

def run_evaluation_for_split(tune_groups, check_groups):
    # Precompute per-claim NLI scores for each answer under Fix 1 + Fix 2 + Fix 3
    # For any claim, we have the passages scored from cache.
    # We can evaluate the full sweep 0.50 - 0.90 in 0.05 steps.
    
    thresholds_sweep = [round(0.50 + 0.05 * i, 2) for i in range(9)] # 0.50 to 0.90
    
    # Pre-extract claims and passage scores for each answer
    answers_data = {}
    for item_id, item in dev_items.items():
        stored = stored_by_id[str(item_id)]
        raw_claims = split_claims(item["answer"], lang=item["lang"])
        passages = _decompose_passages(item["context"])
        
        claims_info = []
        for c_idx, claim_text in enumerate(raw_claims):
            candidates = _select_candidate_passages(claim_text, passages)
            claim_values = _typed_values(claim_text)
            context_values = [_typed_values(p) for p in candidates]
            exact_verdict: str | None = None
            for kind, values in claim_values.items():
                if not values:
                    continue
                has_matching = any(not values.isdisjoint(pv[kind]) for pv in context_values if pv[kind])
                conflicting = [p for p, pv in zip(candidates, context_values) if pv[kind] and values.isdisjoint(pv[kind])]
                if conflicting and not has_matching:
                    exact_verdict = "contradicted"
                    break
            if any(claim_values.values()) and not any(
                values for passage_values in context_values for values in passage_values.values()
            ):
                exact_verdict = "unsupported"
            
            # Cache lookups for candidate scores
            c_scores = []
            for p in candidates:
                k = make_key(p, claim_text)
                entry = cache.get(k)
                if entry is not None:
                    c_scores.append(SimpleNamespace(
                        passage=p,
                        entailment=entry.entailment,
                        neutral=entry.neutral,
                        contradiction=entry.contradiction,
                    ))
            
            claims_info.append({
                "text": claim_text,
                "exact_verdict": exact_verdict,
                "scores": c_scores,
            })
        
        answers_data[item_id] = {
            "item": item,
            "claims_info": claims_info,
            "group": item["group"],
        }
    
    print(f"Total dev items processed: {len(answers_data)}")
    
    def evaluate_at_ethresh(ethresh, group_filter=None):
        traces = []
        for item_id, data in answers_data.items():
            if group_filter and data["group"] not in group_filter:
                continue
            item = data["item"]
            trace_claims = []
            for c in data["claims_info"]:
                c_scores = c["scores"]
                exact_verdict = c["exact_verdict"]
                
                # Fix 1: entailment before contradiction
                if exact_verdict is not None:
                    verdict = exact_verdict
                elif not c_scores:
                    verdict = "unsupported"
                else:
                    best_e = max(c_scores, key=lambda s: s.entailment)
                    if best_e.entailment >= ethresh:
                        verdict = "supported"
                    else:
                        best_c = max(c_scores, key=lambda s: s.contradiction)
                        if best_c.contradiction >= cthresh:
                            verdict = "contradicted"
                        else:
                            verdict = "unsupported"
                
                trace_claims.append({
                    "text": c["text"],
                    "verdict": verdict,
                    "exact_verdict": exact_verdict,
                    "scores": {"entailment": 0.0, "neutral": 0.0, "contradiction": 0.0},
                })
            
            traces.append({
                "id": item["id"],
                "task": item["task"],
                "lang": item["lang"],
                "group": item["group"],
                "claims": trace_claims,
                "gold_spans": item.get("gold_spans", []),
                "answer": item["answer"],
                "context": item["context"],
                "inference_seconds": 0.0,
            })
        
        filtered_items = [data["item"] for item_id, data in answers_data.items() if not group_filter or data["group"] in group_filter]
        eval_rows = [score_policy(item, trace, BASELINE) for item, trace in zip(filtered_items, traces)]
        m = metrics(eval_rows, include_subgroups=False)
        return m
    
    return evaluate_at_ethresh

for method_name, use_sample in [("random.sample", True), ("random.shuffle", False)]:
    print(f"\n================ Method: {method_name} (seed 20261028) ================")
    rng = random.Random(20261028)
    if use_sample:
        tune_g = set(rng.sample(all_groups, 60))
        check_g = set(all_groups) - tune_g
    else:
        shuffled = list(all_groups)
        rng.shuffle(shuffled)
        tune_g = set(shuffled[:60])
        check_g = set(shuffled[60:])
        
    eval_fn = run_evaluation_for_split(tune_g, check_g)
    
    print(f"{'Threshold':<10} | {'Tune Clean Altered':<20} | {'Tune Intercepted':<18} | {'Check Clean Altered':<20} | {'Check Intercepted':<18} | {'Disagreement':<12}")
    print("-" * 106)
    
    for ethresh in [round(0.50 + 0.05 * i, 2) for i in range(9)]:
        m_tune = eval_fn(ethresh, tune_g)
        m_check = eval_fn(ethresh, check_g)
        
        tune_ca_pct = m_tune['false_alterations'] / m_tune['clean'] if m_tune['clean'] else 0.0
        tune_int_pct = m_tune['fully_intercepted'] / m_tune['erroneous'] if m_tune['erroneous'] else 0.0
        check_ca_pct = m_check['false_alterations'] / m_check['clean'] if m_check['clean'] else 0.0
        check_int_pct = m_check['fully_intercepted'] / m_check['erroneous'] if m_check['erroneous'] else 0.0
        
        tune_ca = f"{m_tune['false_alterations']}/{m_tune['clean']} ({tune_ca_pct*100:.2f}%)"
        tune_int = f"{m_tune['fully_intercepted']}/{m_tune['erroneous']} ({tune_int_pct*100:.2f}%)"
        
        check_ca = f"{m_check['false_alterations']}/{m_check['clean']} ({check_ca_pct*100:.2f}%)"
        check_int = f"{m_check['fully_intercepted']}/{m_check['erroneous']} ({check_int_pct*100:.2f}%)"
        
        diff_pct = abs(tune_int_pct - check_int_pct) * 100
        
        print(f"{ethresh:<10.2f} | {tune_ca:<20} | {tune_int:<18} | {check_ca:<20} | {check_int:<18} | {diff_pct:<12.2f}%")

    print("\n--- Overall Development Set (all 120 groups) ---")
    for ethresh in [round(0.50 + 0.05 * i, 2) for i in range(9)]:
        m_all = eval_fn(ethresh, None)
        ca_pct = m_all['false_alterations'] / m_all['clean'] if m_all['clean'] else 0.0
        int_pct = m_all['fully_intercepted'] / m_all['erroneous'] if m_all['erroneous'] else 0.0
        print(f"ethresh={ethresh:.2f} | clean_altered={m_all['false_alterations']}/{m_all['clean']} ({ca_pct*100:.2f}%) | intercepted={m_all['fully_intercepted']}/{m_all['erroneous']} ({int_pct*100:.2f}%) | char_prec={m_all['character_precision']:.4f}")
