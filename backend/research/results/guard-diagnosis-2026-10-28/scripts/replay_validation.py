"""Replay VALIDATION split for original baseline code and current HEAD code (Fix 3 only)."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import sys
from types import SimpleNamespace

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from backend.research.guard.claims import split_claims
import backend.research.guard.claims as c_mod
from backend.research.guard.nli import _decompose_passages, _select_candidate_passages, _typed_values
from backend.research.guard.guard import _thresholds
from backend.research.guard.action_policy import BASELINE, should_alter
from backend.research.guard.eval_external import removal_mask
from backend.research.replay.cache import NLICache, make_key
from backend.research.run_guard_calibration import load_inputs, selected_items, score_policy, metrics

CACHE_PATH = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/nli_cache_validation.jsonl"
RAG_RESPONSE_PATH = repo_root / "backend/research/results/guard-external-2026-10-26/data/rag-response.jsonl"


def run_validation_replay():
    print("=" * 80)
    print("VALIDATION SPLIT REPLAY: BASELINE vs CURRENT HEAD (FIX 3 ONLY)")
    print("=" * 80)

    manifest, responses = load_inputs()
    val_items = {item["id"]: item for item in selected_items(manifest, responses, "validation")}
    print(f"Loaded {len(val_items)} validation split items.")

    cache = NLICache(CACHE_PATH)
    print(f"Loaded validation cache with {len(cache)} entries.")

    rag_labels_by_id = {}
    if RAG_RESPONSE_PATH.exists():
        with RAG_RESPONSE_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r.get("labels"):
                    rag_labels_by_id[str(r["id"])] = r["labels"]

    _, thresholds = _thresholds("en")

    def run_eval(use_fix3: bool):
        orig_pats = c_mod._NON_CLAIM_PATTERNS
        orig_non_fac = set(c_mod._NON_FACTUAL)
        if not use_fix3:
            c_mod._NON_CLAIM_PATTERNS = ()
            if "sure" in c_mod._NON_FACTUAL:
                c_mod._NON_FACTUAL.remove("sure")

        traces = []
        for tid, item in val_items.items():
            passages = _decompose_passages(item["context"])
            claims = split_claims(item["answer"], lang=item["lang"])
            re_claims = []
            for c in claims:
                candidates = _select_candidate_passages(c, passages, max_candidates=4)
                c_val = _typed_values(c)
                context_values = [_typed_values(p) for p in candidates]

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
                if any(cs is None for cs in c_scores):
                    raise KeyError(f"Missing cache entry for claim: {c}")

                if exact_verdict is not None:
                    verdict = exact_verdict
                    best_idx = 0
                elif not c_scores:
                    verdict = "unsupported"
                    best_idx = 0
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

                winning = c_scores[best_idx] if c_scores else SimpleNamespace(entailment=0.0, neutral=1.0, contradiction=0.0)
                re_claims.append({
                    "text": c,
                    "verdict": verdict,
                    "exact_verdict": exact_verdict,
                    "scores": vars(winning),
                })

            traces.append({
                "id": tid,
                "task": item["task"],
                "quality": item["quality"],
                "gold_spans": item.get("gold_spans", []),
                "claims": re_claims,
                "answer": item["answer"],
                "context": item["context"],
                "inference_seconds": 0.0,
            })

        c_mod._NON_CLAIM_PATTERNS = orig_pats
        c_mod._NON_FACTUAL = orig_non_fac

        by_id = {str(t["id"]): t for t in traces}
        eval_rows = [score_policy(item, by_id[item["id"]], BASELINE) for item in val_items.values()]
        m = metrics(eval_rows, include_subgroups=False)

        # Label-type interception
        label_totals = defaultdict(int)
        label_intercepted = defaultdict(int)
        for item in val_items.values():
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

        by_type = {
            lt: f"{label_intercepted[lt]}/{label_totals[lt]} ({label_intercepted[lt]/label_totals[lt]*100:.1f}%)"
            for lt in sorted(label_totals.keys())
        }
        inter_ids = {r["id"] for r in eval_rows if r["gold_error"] and r["spans"]["fully_intercepted"]}

        return {
            "metrics": m,
            "eval_rows": eval_rows,
            "inter_ids": inter_ids,
            "by_type": by_type,
            "by_id": by_id,
        }

    res_base = run_eval(use_fix3=False)
    res_head = run_eval(use_fix3=True)

    gained = sorted(list(res_head["inter_ids"] - res_base["inter_ids"]), key=int)
    lost = sorted(list(res_base["inter_ids"] - res_head["inter_ids"]), key=int)

    print("\n--- RESULTS TABLE ---")
    print(f"{'Config':<12} | {'Clean Altered':<22} | {'Intercepted':<22} | {'Char Prec':<10} | {'Gained vs Base':<16} | {'Lost vs Base'}")
    print("-" * 105)

    mb = res_base["metrics"]
    ca_b = f"{mb['false_alterations']}/{mb['clean']} ({mb['false_alteration_rate']*100:.2f}%)"
    ei_b = f"{mb['fully_intercepted']}/{mb['erroneous']} ({mb['fully_intercepted_rate']*100:.2f}%)"
    cp_b = f"{mb['character_precision']:.4f}"
    print(f"{'Baseline':<12} | {ca_b:<22} | {ei_b:<22} | {cp_b:<10} | {'0 []':<16} | {'0 []'}")

    mh = res_head["metrics"]
    ca_h = f"{mh['false_alterations']}/{mh['clean']} ({mh['false_alteration_rate']*100:.2f}%)"
    ei_h = f"{mh['fully_intercepted']}/{mh['erroneous']} ({mh['fully_intercepted_rate']*100:.2f}%)"
    cp_h = f"{mh['character_precision']:.4f}"
    g_str = f"+{len(gained)} {gained}" if gained else "0 []"
    l_str = f"-{len(lost)} {lost}" if lost else "0 []"
    print(f"{'HEAD (Fix 3)':<12} | {ca_h:<22} | {ei_h:<22} | {cp_h:<10} | {g_str:<16} | {l_str}")

    print("\n--- Interception by Label Type ---")
    print("Baseline:")
    for lt, s in res_base["by_type"].items():
        print(f"  {lt:24}: {s}")

    print("\nHEAD (Fix 3):")
    for lt, s in res_head["by_type"].items():
        print(f"  {lt:24}: {s}")

    return {
        "baseline": res_base,
        "head": res_head,
        "gained": gained,
        "lost": lost,
    }


if __name__ == "__main__":
    run_validation_replay()
