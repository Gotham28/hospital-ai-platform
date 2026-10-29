"""Operating-point sweep on HEAD (baseline + Fix 3).

Sweeps:
  - contradiction threshold: {0.5, 0.7, 0.9}
  - neutral/unsupported handling: {redact, ignore, N>=0.8, N>=0.95}
  - entailment threshold: {0.5, 0.6, 0.7, 0.8, 0.9}
Total: 3 x 4 x 5 = 60 operating points.

Evaluated on BOTH development (720 responses) and validation (360 responses) splits.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from backend.research.guard.claims import split_claims
from backend.research.guard.nli import _decompose_passages, _select_candidate_passages, _typed_values
from backend.research.guard.eval_external import removal_mask, score_spans
from backend.research.replay.cache import NLICache, make_key
from backend.research.run_guard_calibration import load_inputs, selected_items, metrics

DEV_CACHE_PATH = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl"
VAL_CACHE_PATH = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/nli_cache_validation.jsonl"
OUT_PATH = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/operating_points.json"


def precompute_split(split_name: str, items: dict, cache: NLICache):
    """Precompute for each answer: raw text, length, gold_spans, and per-claim data."""
    data = []
    for tid, item in items.items():
        answer = item["answer"]
        passages = _decompose_passages(item["context"])
        claims = split_claims(answer, lang=item["lang"])
        
        claims_data = []
        for c in claims:
            candidates = _select_candidate_passages(c, passages, max_candidates=4)
            c_val = _typed_values(c)
            context_values = [_typed_values(p) for p in candidates]
            
            exact_v = None
            for kind, values in c_val.items():
                if not values:
                    continue
                conflicting = [p for p, pv in zip(candidates, context_values) if pv[kind] and values.isdisjoint(pv[kind])]
                if conflicting:
                    exact_v = "contradicted"
                    break
            if any(c_val.values()) and not any(values for pv in context_values for values in pv.values()):
                exact_v = "unsupported"
            
            scores = [cache.get(make_key(p, c)) for p in candidates]
            if not scores:
                best_s = None
            else:
                best_idx = max(range(len(scores)), key=lambda i: max(scores[i].entailment, scores[i].contradiction))
                best_s = scores[best_idx]
                
            claims_data.append({
                "text": c,
                "exact_verdict": exact_v,
                "best_scores": best_s,
            })
            
        data.append({
            "id": tid,
            "group": item["group"],
            "task": item["task"],
            "quality": item["quality"],
            "gold_spans": item.get("gold_spans", []),
            "gold_error": bool(item.get("gold_spans", [])),
            "answer": answer,
            "answer_len": len(answer),
            "claims": claims_data,
        })
    return data


def eval_operating_point(data: list[dict], c_thresh: float, n_mode: str, e_thresh: float):
    """Evaluate one operating point over precomputed split data."""
    rows = []
    clean_total_chars = 0
    clean_redacted_chars = 0
    clean_redacted_fractions = []
    
    for item in data:
        answer = item["answer"]
        final = answer
        item_claims = []
        
        for c in item["claims"]:
            exact_v = c["exact_verdict"]
            best = c["best_scores"]
            
            # Determine verdict under (c_thresh, e_thresh)
            if exact_v is not None:
                verdict = exact_v
            elif best is None:
                verdict = "unsupported"
            elif best.contradiction >= c_thresh and best.contradiction > best.entailment:
                verdict = "contradicted"
            elif best.entailment >= e_thresh:
                verdict = "supported"
            else:
                verdict = "unsupported"
                
            # Determine altered under n_mode
            if verdict == "supported":
                altered = False
            elif verdict == "contradicted":
                altered = True
            elif verdict == "unsupported":
                if n_mode == "redact":
                    altered = True
                elif n_mode == "ignore":
                    altered = False
                elif n_mode == "N>=0.8":
                    altered = (best is not None and best.neutral >= 0.8)
                elif n_mode == "N>=0.95":
                    altered = (best is not None and best.neutral >= 0.95)
                else:
                    raise ValueError(f"Unknown n_mode: {n_mode}")
            else:
                altered = False
                
            item_claims.append({
                "text": c["text"],
                "verdict": verdict,
                "altered": altered,
            })
            if altered:
                final = final.replace(c["text"], "[FLAG_TEXT]")
                
        result = dict(final_answer=final, claims=item_claims)
        mask = removal_mask(answer, result)
        spans = score_spans(answer, item["gold_spans"], mask)
        
        # Track clean redactions
        if not item["gold_error"]:
            clean_total_chars += item["answer_len"]
            n_redacted = len(mask)
            clean_redacted_chars += n_redacted
            clean_redacted_fractions.append(n_redacted / item["answer_len"] if item["answer_len"] > 0 else 0.0)
            
        rows.append(dict(
            id=item["id"],
            group=item["group"],
            task=item["task"],
            quality=item["quality"],
            gold_error=item["gold_error"],
            predicted_error=any(c["verdict"] in {"unsupported", "contradicted"} for c in item_claims),
            changed=bool(mask),
            spans=spans,
            inference_seconds=0.0,
        ))
        
    m = metrics(rows, include_subgroups=False)
    
    clean_char_redact_micro = clean_redacted_chars / clean_total_chars if clean_total_chars > 0 else 0.0
    clean_char_redact_macro = sum(clean_redacted_fractions) / len(clean_redacted_fractions) if clean_redacted_fractions else 0.0
    
    return {
        "clean_altered": m["false_alterations"],
        "clean_total": m["clean"],
        "clean_altered_pct": round(m["false_alterations"] / m["clean"] * 100, 2),
        "intercepted": m["fully_intercepted"],
        "erroneous_total": m["erroneous"],
        "intercepted_pct": round(m["fully_intercepted"] / m["erroneous"] * 100, 2),
        "char_precision": round(m["character_precision"], 4) if m["character_precision"] is not None else 0.0,
        "clean_char_redact_micro": round(clean_char_redact_micro, 4),
        "clean_char_redact_macro": round(clean_char_redact_macro, 4),
    }


def main():
    print("Loading data and caches...")
    manifest, responses = load_inputs()
    dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}
    val_items = {item["id"]: item for item in selected_items(manifest, responses, "validation")}
    
    dev_cache = NLICache(DEV_CACHE_PATH)
    val_cache = NLICache(VAL_CACHE_PATH)
    
    print(f"Precomputing dev split ({len(dev_items)} items)...")
    dev_pre = precompute_split("development", dev_items, dev_cache)
    print(f"Precomputing val split ({len(val_items)} items)...")
    val_pre = precompute_split("validation", val_items, val_cache)
    
    c_thresholds = [0.5, 0.7, 0.9]
    n_modes = ["redact", "ignore", "N>=0.8", "N>=0.95"]
    e_thresholds = [0.5, 0.6, 0.7, 0.8, 0.9]
    
    print(f"Running sweep: {len(c_thresholds)} C x {len(n_modes)} N x {len(e_thresholds)} E = {len(c_thresholds)*len(n_modes)*len(e_thresholds)} operating points...")
    
    all_results = []
    
    for c_t in c_thresholds:
        for n_m in n_modes:
            for e_t in e_thresholds:
                dev_res = eval_operating_point(dev_pre, c_t, n_m, e_t)
                val_res = eval_operating_point(val_pre, c_t, n_m, e_t)
                
                point_id = f"ct{c_t}_n{n_m}_et{e_t}"
                rec = {
                    "point_id": point_id,
                    "c_thresh": c_t,
                    "n_mode": n_m,
                    "e_thresh": e_t,
                    "development": dev_res,
                    "validation": val_res,
                }
                all_results.append(rec)
                
    # Save results
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"Saved {len(all_results)} operating points to {OUT_PATH}")
    
    # Pareto frontier calculation
    # We want: for each interception level, minimize clean_altered (or maximize precision)
    # A point A dominates point B if:
    # A.intercepted >= B.intercepted AND A.clean_altered <= B.clean_altered, with at least one strict inequality.
    print("\nComputing Pareto frontiers...")
    
    def get_pareto_frontier(results: list[dict], split_key: str):
        frontier = []
        for p in results:
            p_res = p[split_key]
            p_inter = p_res["intercepted"]
            p_clean = p_res["clean_altered"]
            
            # Check if dominated by any other point
            dominated = False
            for o in results:
                o_res = o[split_key]
                o_inter = o_res["intercepted"]
                o_clean = o_res["clean_altered"]
                
                if (o_inter >= p_inter and o_clean <= p_clean) and (o_inter > p_inter or o_clean < p_clean):
                    dominated = True
                    break
            if not dominated:
                frontier.append(p)
                
        # Sort by intercepted ascending (or clean_altered ascending)
        frontier.sort(key=lambda x: (x[split_key]["intercepted"], x[split_key]["clean_altered"]))
        return frontier

    dev_frontier = get_pareto_frontier(all_results, "development")
    val_frontier = get_pareto_frontier(all_results, "validation")
    
    # Combined frontier points (points on dev frontier or val frontier, or Pareto across both)
    print(f"Dev Pareto frontier points: {len(dev_frontier)}")
    print(f"Val Pareto frontier points: {len(val_frontier)}")
    
    # Print sample comparison table
    print("\n" + "=" * 120)
    print("ALL 60 OPERATING POINTS: DEVELOPMENT vs VALIDATION")
    print("=" * 120)
    hdr = f"{'Point ID':<20} | {'Dev Clean Alt':<16} | {'Dev Intercept':<16} | {'Dev Prec':<9} | {'Dev ChRed':<10} | {'Val Clean Alt':<16} | {'Val Intercept':<16} | {'Val Prec':<9} | {'Val ChRed':<10}"
    print(hdr)
    print("-" * len(hdr))
    
    for r in all_results:
        d = r["development"]
        v = r["validation"]
        d_ca = f"{d['clean_altered']}/{d['clean_total']} ({d['clean_altered_pct']:.1f}%)"
        d_int = f"{d['intercepted']}/{d['erroneous_total']} ({d['intercepted_pct']:.1f}%)"
        v_ca = f"{v['clean_altered']}/{v['clean_total']} ({v['clean_altered_pct']:.1f}%)"
        v_int = f"{v['intercepted']}/{v['erroneous_total']} ({v['intercepted_pct']:.1f}%)"
        print(f"{r['point_id']:<20} | {d_ca:<16} | {d_int:<16} | {d['char_precision']:<9.4f} | {d['clean_char_redact_micro']:<10.4f} | {v_ca:<16} | {v_int:<16} | {v['char_precision']:<9.4f} | {v['clean_char_redact_micro']:<10.4f}")


if __name__ == "__main__":
    main()
