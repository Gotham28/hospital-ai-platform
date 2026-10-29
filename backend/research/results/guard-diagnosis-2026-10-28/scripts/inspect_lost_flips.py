import sys
import json
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from backend.research.guard.claims import split_claims
from backend.research.guard.nli import _decompose_passages, _select_candidate_passages, _typed_values
from backend.research.replay.cache import NLICache, make_key
from backend.research.run_guard_calibration import load_inputs, selected_items

cache_path = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl"
cache = NLICache(cache_path)

manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}

rag_response_path = repo_root / "backend/research/results/guard-external-2026-10-26/data/rag-response.jsonl"
rag_by_id = {}
with open(rag_response_path, "r", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        rag_by_id[str(r["id"])] = r

target_ids = ["285", "4600", "10263", "11252", "7887"]

for aid in target_ids:
    item = dev_items[aid]
    rag_r = rag_by_id[aid]
    
    print("\n" + "=" * 80)
    print(f"ANSWER ID: {aid} (Task: {item['task']})")
    print("=" * 80)
    print("Gold Spans & Labels:")
    for gsi, gs in enumerate(item.get("gold_spans", [])):
        gst = item['answer'][gs[0]:gs[1]]
        lbl = rag_r.get("labels", [])[gsi] if gsi < len(rag_r.get("labels", [])) else "unknown"
        print(f"  Span [{gsi}] ({lbl}): {repr(gst)}")
        
    passages = _decompose_passages(item["context"])
    claims = split_claims(item["answer"], lang=item["lang"])
    
    for ci, c in enumerate(claims):
        candidates = _select_candidate_passages(c, passages, max_candidates=4)
        c_scores = [cache.get(make_key(p, c)) for p in candidates]
        
        # Check baseline verdict vs Fix 1/2 verdict
        # Baseline: max(entailment, contradiction)
        best_base = max(range(len(c_scores)), key=lambda i: max(c_scores[i].entailment, c_scores[i].contradiction))
        s_base = c_scores[best_base]
        if s_base.contradiction >= 0.50 and s_base.contradiction > s_base.entailment:
            v_base = "contradicted"
        elif s_base.entailment >= 0.90:
            v_base = "supported"
        else:
            v_base = "unsupported"
            
        # Fix 1: best entailment first
        best_e_idx = max(range(len(c_scores)), key=lambda i: c_scores[i].entailment)
        s_e = c_scores[best_e_idx]
        if s_e.entailment >= 0.90:
            v_fix1 = "supported"
            winning_p = candidates[best_e_idx]
            winning_s = s_e
        else:
            best_c_idx = max(range(len(c_scores)), key=lambda i: c_scores[i].contradiction)
            s_c = c_scores[best_c_idx]
            if s_c.contradiction >= 0.50:
                v_fix1 = "contradicted"
                winning_p = candidates[best_c_idx]
                winning_s = s_c
            else:
                v_fix1 = "unsupported"
                winning_p = candidates[best_e_idx]
                winning_s = s_e
                
        # Fix 2 check (numeric)
        claim_values = _typed_values(c)
        context_values = [_typed_values(p) for p in candidates]
        exact_verdict_old = None
        exact_verdict_new = None
        for kind, values in claim_values.items():
            if not values: continue
            conflicting = [p for p, pv in zip(candidates, context_values) if pv[kind] and values.isdisjoint(pv[kind])]
            has_matching = any(not values.isdisjoint(pv[kind]) for pv in context_values if pv[kind])
            if conflicting:
                exact_verdict_old = "contradicted"
            if conflicting and not has_matching:
                exact_verdict_new = "contradicted"
        
        # Report if this claim changed verdict
        if (aid != "7887" and v_base != v_fix1) or (aid == "7887" and exact_verdict_old != exact_verdict_new):
            print(f"\n>>> CLAIM {ci} FLIPPED VERDICT: {repr(c)}")
            print(f"    Baseline verdict: {v_base} (via passage with E={s_base.entailment:.4f}, N={s_base.neutral:.4f}, C={s_base.contradiction:.4f})")
            if aid != "7887":
                print(f"    Fix 1 verdict   : {v_fix1}")
                print(f"    Winning passage (Index {best_e_idx}): {repr(winning_p)}")
                print(f"    Winning passage scores: E={winning_s.entailment:.4f}, N={winning_s.neutral:.4f}, C={winning_s.contradiction:.4f}")
            else:
                print(f"    Old Exact Verdict: {exact_verdict_old} -> New Exact Verdict: {exact_verdict_new}")
                print(f"    Claim values: {claim_values}")
                for pi, (p, pv) in enumerate(zip(candidates, context_values)):
                    print(f"    Passage {pi} values: {pv} | text: {repr(p[:100])}...")
            
            # Print all candidates E/N/C
            print("    All Candidate Passages:")
            for pi, (p, sc) in enumerate(zip(candidates, c_scores)):
                print(f"      [Cand {pi}]: E={sc.entailment:.4f}, N={sc.neutral:.4f}, C={sc.contradiction:.4f} | {repr(p[:120])}...")
