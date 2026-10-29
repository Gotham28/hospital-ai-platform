import sys
import json
from collections import defaultdict, Counter
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

# Run {3} (Fix 3 alone) vs {3,1} (Fix 3 + Fix 1)
# Note: Fix 2 is reverted, so exact_verdict uses original numeric contradiction rule
def get_traces(include_fix1: bool):
    traces = []
    for item_id, item in dev_items.items():
        stored = stored_by_id[item_id]
        raw_claims = split_claims(item["answer"], lang=item["lang"])
        passages = _decompose_passages(item["context"])
        re_claims = []
        for c in raw_claims:
            candidates = _select_candidate_passages(c, passages, max_candidates=4)
            c_val = _typed_values(c)
            context_values = [_typed_values(p) for p in candidates]
            
            # Original numeric rule (Fix 2 reverted)
            exact_verdict = None
            for kind, values in c_val.items():
                if not values:
                    continue
                conflicting = [p for p, pv in zip(candidates, context_values) if pv[kind] and values.isdisjoint(pv[kind])]
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
                best_e_idx = max(range(len(c_scores)), key=lambda i: c_scores[i].entailment)
                if c_scores[best_e_idx].entailment >= 0.90:
                    verdict = "supported"
                    best_idx = best_e_idx
                else:
                    best_c_idx = max(range(len(c_scores)), key=lambda i: c_scores[i].contradiction)
                    if c_scores[best_c_idx].contradiction >= 0.50:
                        verdict = "contradicted"
                        best_idx = best_c_idx
                    else:
                        verdict = "unsupported"
                        best_idx = best_e_idx
            else:
                best_base_idx = max(range(len(c_scores)), key=lambda i: max(c_scores[i].entailment, c_scores[i].contradiction))
                s = c_scores[best_base_idx]
                if s.contradiction >= 0.50 and s.contradiction > s.entailment:
                    verdict = "contradicted"
                elif s.entailment >= 0.90:
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
            "task": item["task"],
            "quality": item["quality"],
            "gold_spans": item.get("gold_spans", []),
            "claims": re_claims,
            "answer": item["answer"],
            "inference_seconds": 0.0,
        })
    return traces

t_fix3 = get_traces(include_fix1=False)
t_fix31 = get_traces(include_fix1=True)

# Map by answer id
by_id_fix3 = {str(t["id"]): t for t in t_fix3}
by_id_fix31 = {str(t["id"]): t for t in t_fix31}

# Metrics
eval_rows_fix3 = [score_policy(item, by_id_fix3[item["id"]], BASELINE) for item in dev_items.values()]
m_fix3 = metrics(eval_rows_fix3, include_subgroups=False)

eval_rows_fix31 = [score_policy(item, by_id_fix31[item["id"]], BASELINE) for item in dev_items.values()]
m_fix31 = metrics(eval_rows_fix31, include_subgroups=False)

print("=== Metrics After Fix 2 Revert ===")
print(f"{{3}}  : clean_altered={m_fix3['false_alterations']}/{m_fix3['clean']} ({m_fix3['false_alteration_rate']*100:.2f}%), intercepted={m_fix3['fully_intercepted']}/{m_fix3['erroneous']} ({m_fix3['fully_intercepted_rate']*100:.2f}%), char_prec={m_fix3['character_precision']:.4f}")
print(f"{{3,1}}: clean_altered={m_fix31['false_alterations']}/{m_fix31['clean']} ({m_fix31['false_alteration_rate']*100:.2f}%), intercepted={m_fix31['fully_intercepted']}/{m_fix31['erroneous']} ({m_fix31['fully_intercepted_rate']*100:.2f}%), char_prec={m_fix31['character_precision']:.4f}")

# Compare claims
flips_by_dir = Counter()
flips_by_task = defaultdict(Counter)
flips_details = []

for item_id, item in dev_items.items():
    c_f3 = by_id_fix3[item_id]["claims"]
    c_f31 = by_id_fix31[item_id]["claims"]
    task = item["task"]
    
    for ci, (c1, c2) in enumerate(zip(c_f3, c_f31)):
        v1 = c1["verdict"]
        v2 = c2["verdict"]
        if v1 != v2:
            direction = f"{v1} -> {v2}"
            flips_by_dir[direction] += 1
            flips_by_task[task][direction] += 1
            flips_details.append({
                "answer_id": item_id,
                "task": task,
                "claim_idx": ci,
                "claim_text": c1["text"],
                "v_fix3": v1,
                "v_fix31": v2,
            })

print(f"\nTotal claim verdict flips between {{3}} and {{3,1}}: {len(flips_details)}")
print(f"Flips by direction: {dict(flips_by_dir)}")

print("\nFlips by task and direction:")
for task in sorted(flips_by_task.keys()):
    print(f"  {task:15}: {dict(flips_by_task[task])}")

# Answers cleared (clean answers that were altered in {3} but NOT altered in {3,1})
cleared_answers = []
for r3, r31 in zip(eval_rows_fix3, eval_rows_fix31):
    if not r3["gold_error"]: # clean answer
        if r3["changed"] and not r31["changed"]:
            cleared_answers.append(r3["id"])

print(f"\nClean answers cleared by Fix 1 (count={len(cleared_answers)}): {cleared_answers}")
for aid in cleared_answers:
    item = dev_items[aid]
    print(f"  Answer {aid} ({item['task']}):")
    for ci, (c1, c2) in enumerate(zip(by_id_fix3[aid]["claims"], by_id_fix31[aid]["claims"])):
        if c1["verdict"] != c2["verdict"]:
            print(f"    Claim {ci}: {repr(c1['text'][:80])} [{c1['verdict']} -> {c2['verdict']}]")

# Lost erroneous answers
inter_f3 = {r["id"] for r in eval_rows_fix3 if r["gold_error"] and r["spans"]["fully_intercepted"]}
inter_f31 = {r["id"] for r in eval_rows_fix31 if r["gold_error"] and r["spans"]["fully_intercepted"]}
lost_err = sorted(list(inter_f3 - inter_f31), key=lambda x: int(x))
print(f"\nErroneous answers that lost interception in {{3,1}} vs {{3}}: {lost_err}")
