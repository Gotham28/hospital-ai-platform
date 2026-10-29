import sys
import json
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from backend.research.guard.claims import split_claims
from backend.research.guard.nli import _decompose_passages, _select_candidate_passages, _typed_values
from backend.research.guard.action_policy import BASELINE, should_alter
from backend.research.guard.eval_external import removal_mask
from backend.research.replay.cache import NLICache, make_key
from backend.research.run_guard_calibration import load_inputs, selected_items, score_policy, metrics

cache_path = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl"
cache = NLICache(cache_path)

manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}

traces_path = repo_root / "backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl"
stored_by_id = {str(json.loads(line)["id"]): json.loads(line) for line in traces_path.read_text(encoding="utf-8").splitlines()}

rag_response_path = repo_root / "backend/research/results/guard-external-2026-10-26/data/rag-response.jsonl"
rag_labels_by_id = {}
with open(rag_response_path, "r", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("labels"):
            rag_labels_by_id[str(r["id"])] = r["labels"]

ethresh = 0.90
cthresh = 0.50

def run_combo(include_fix1: bool, include_fix2: bool, include_fix3: bool):
    traces = []
    for item_id, item in dev_items.items():
        stored = stored_by_id[item_id]
        if include_fix3:
            raw_claims = split_claims(item["answer"], lang=item["lang"])
        else:
            raw_claims = [c["text"] for c in stored["claims"]]
            
        passages = _decompose_passages(item["context"])
        re_claims = []
        for c in raw_claims:
            candidates = _select_candidate_passages(c, passages, max_candidates=4)
            c_val = _typed_values(c)
            context_values = [_typed_values(p) for p in candidates]
            
            exact_verdict = None
            for kind, values in c_val.items():
                if not values:
                    continue
                conflicting = [p for p, pv in zip(candidates, context_values) if pv[kind] and values.isdisjoint(pv[kind])]
                has_matching = any(not values.isdisjoint(pv[kind]) for pv in context_values if pv[kind])
                if include_fix2:
                    if conflicting and not has_matching:
                        exact_verdict = "contradicted"
                        break
                else:
                    if conflicting:
                        exact_verdict = "contradicted"
                        break
            if any(c_val.values()) and not any(values for pv in context_values for values in pv.values()):
                exact_verdict = "unsupported"
                
            c_scores = [cache.get(make_key(p, c)) for p in candidates]
            
            if exact_verdict is not None:
                verdict = exact_verdict
                best_idx = 0
            elif not c_scores:
                verdict = "unsupported"
                best_idx = 0
            elif include_fix1:
                # Fix 1: entailment before contradiction
                best_e_idx = max(range(len(c_scores)), key=lambda i: c_scores[i].entailment)
                if c_scores[best_e_idx].entailment >= ethresh:
                    verdict = "supported"
                    best_idx = best_e_idx
                else:
                    best_c_idx = max(range(len(c_scores)), key=lambda i: c_scores[i].contradiction)
                    if c_scores[best_c_idx].contradiction >= cthresh:
                        verdict = "contradicted"
                        best_idx = best_c_idx
                    else:
                        verdict = "unsupported"
                        best_idx = best_e_idx
            else:
                # Baseline passage selection: max(entailment, contradiction)
                best_base_idx = max(range(len(c_scores)), key=lambda i: max(c_scores[i].entailment, c_scores[i].contradiction))
                s = c_scores[best_base_idx]
                if s.contradiction >= cthresh and s.contradiction > s.entailment:
                    verdict = "contradicted"
                elif s.entailment >= ethresh:
                    verdict = "supported"
                else:
                    verdict = "unsupported"
                best_idx = best_base_idx
                
            winning_scores = c_scores[best_idx] if c_scores else SimpleNamespace(entailment=0.0, neutral=1.0, contradiction=0.0)
            re_claims.append({
                "text": c,
                "verdict": verdict,
                "exact_verdict": exact_verdict,
                "scores": {
                    "entailment": winning_scores.entailment,
                    "neutral": winning_scores.neutral,
                    "contradiction": winning_scores.contradiction,
                }
            })
            
        traces.append({
            "id": item_id,
            "group": item["group"],
            "task": item["task"],
            "quality": item["quality"],
            "gold_spans": item.get("gold_spans", []),
            "claims": re_claims,
            "answer": item["answer"],
            "inference_seconds": 0.0,
        })
        
    by_id = {str(t["id"]): t for t in traces}
    eval_rows = [score_policy(item, by_id[item["id"]], BASELINE) for item in dev_items.values()]
    m = metrics(eval_rows, include_subgroups=False)
    
    # Label type interception
    label_totals = defaultdict(int)
    label_intercepted = defaultdict(int)
    for item in dev_items.values():
        tid = str(item["id"])
        labels = rag_labels_by_id.get(tid, [])
        if not labels:
            continue
        trace_row = by_id[tid]
        answer = item["answer"]
        final = answer
        claims_list = []
        for claim in trace_row["claims"]:
            altered = should_alter(claim["verdict"], SimpleNamespace(**claim["scores"]), claim["exact_verdict"], BASELINE)
            claims_list.append(dict(text=claim["text"], verdict=claim["verdict"], altered=altered))
            if altered:
                final = final.replace(claim["text"], "[FLAG_TEXT]")
        mask = removal_mask(answer, dict(final_answer=final, claims=claims_list))
        for lbl in labels:
            l_type = lbl["label_type"]
            span_set = set(range(lbl["start"], lbl["end"]))
            label_totals[l_type] += 1
            if span_set <= mask:
                label_intercepted[l_type] += 1
                
    by_type = {lt: f"{label_intercepted[lt]}/{label_totals[lt]} ({label_intercepted[lt]/label_totals[lt]*100:.1f}%)" for lt in sorted(label_totals.keys())}
    
    return {
        "metrics": m,
        "eval_rows": eval_rows,
        "by_type": by_type,
    }

base_res = run_combo(False, False, False)
base_inter = {row["id"] for row in base_res["eval_rows"] if row["gold_error"] and row["spans"]["fully_intercepted"]}

combos = [
    ("{3}", False, False, True),
    ("{3,1}", True, False, True),
    ("{3,2}", False, True, True),
    ("{3,1,2}", True, True, True),
]

print("=" * 90)
print(f"{'Combo':<10} | {'Clean Altered':<20} | {'Intercepted':<20} | {'Char Prec':<10} | {'Lost IDs'}")
print("=" * 90)

results_matrix = {}
for name, f1, f2, f3 in combos:
    res = run_combo(f1, f2, f3)
    m = res["metrics"]
    curr_inter = {row["id"] for row in res["eval_rows"] if row["gold_error"] and row["spans"]["fully_intercepted"]}
    lost = sorted(list(base_inter - curr_inter), key=lambda x: int(x))
    
    ca = f"{m['false_alterations']}/{m['clean']} ({m['false_alterations']/m['clean']*100:.2f}%)"
    ei = f"{m['fully_intercepted']}/{m['erroneous']} ({m['fully_intercepted']/m['erroneous']*100:.2f}%)"
    cp = f"{m['character_precision']:.4f}"
    
    print(f"{name:<10} | {ca:<20} | {ei:<20} | {cp:<10} | {lost}")
    results_matrix[name] = {
        "clean_altered": ca,
        "intercepted": ei,
        "char_precision": cp,
        "lost_ids": lost,
        "by_type": res["by_type"],
    }

print("\n--- By Label Type ---")
for name in ["{3}", "{3,1}", "{3,2}", "{3,1,2}"]:
    print(f"\nCombo {name}:")
    for lt, val in results_matrix[name]["by_type"].items():
        print(f"  {lt:24}: {val}")
