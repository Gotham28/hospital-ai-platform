import sys
import json
from collections import defaultdict, Counter
from pathlib import Path
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from backend.research.guard.claims import split_claims
from backend.research.guard.nli import _select_candidate_passages, _typed_values, _decompose_passages
from backend.research.guard.action_policy import BASELINE, should_alter
from backend.research.guard.eval_external import removal_mask
from backend.research.replay.cache import NLICache, make_key
from backend.research.run_guard_calibration import load_inputs, selected_items, score_policy, metrics

base_cache_path = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl"
base_cache = NLICache(base_cache_path)

chunk_cache_path = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/nli_cache_chunking.jsonl"
chunk_cache = NLICache(chunk_cache_path)

def get_score(p: str, c: str):
    k = make_key(p, c)
    val = chunk_cache.get(k)
    if val is not None:
        return val
    return base_cache.get(k)

manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}

traces_path = repo_root / "backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl"
stored_by_id = {str(json.loads(line)["id"]): json.loads(line) for line in traces_path.read_text(encoding="utf-8").splitlines()}

rag_response_path = repo_root / "backend/research/results/guard-external-2026-10-26/data/rag-response.jsonl"
rag_by_id = {}
with open(rag_response_path, "r", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("labels"):
            rag_by_id[str(r["id"])] = r

# We need the old _decompose_passages (before Fix 5) for {3} and baseline
import re
def decompose_old(passages: list[str]) -> list[str]:
    chunks: list[str] = []
    for p in passages:
        paragraphs = [para.strip() for para in re.split(r"\n\s*\n+", p) if para.strip()]
        if len(paragraphs) > 1:
            for para in paragraphs:
                if len(para) <= 500:
                    chunks.append(para)
                else:
                    sents = re.split(r"(?<=[.!?])\s+", para)
                    buf, buf_len = [], 0
                    for s in sents:
                        buf.append(s)
                        buf_len += len(s)
                        if buf_len >= 350:
                            chunks.append(" ".join(buf))
                            buf, buf_len = [], 0
                    if buf:
                        chunks.append(" ".join(buf))
        elif len(p) > 500:
            sents = re.split(r"(?<=[.!?])\s+", p)
            buf, buf_len = [], 0
            for s in sents:
                buf.append(s)
                buf_len += len(s)
                if buf_len >= 350:
                    chunks.append(" ".join(buf))
                    buf, buf_len = [], 0
            if buf:
                chunks.append(" ".join(buf))
        else:
            chunks.append(p)
    return chunks or passages

# New _decompose_passages is current HEAD _decompose_passages from nli.py
from backend.research.guard.nli import _decompose_passages as decompose_new

def run_simulation(use_new_chunking: bool, include_fix1: bool, is_baseline: bool = False):
    traces = []
    for item_id, item in dev_items.items():
        stored = stored_by_id[item_id]
        if is_baseline:
            raw_claims = [c["text"] for c in stored["claims"]]
        else:
            raw_claims = split_claims(item["answer"], lang=item["lang"]) # Fix 3
            
        passages = decompose_new(item["context"]) if use_new_chunking else decompose_old(item["context"])
        
        re_claims = []
        for c in raw_claims:
            candidates = _select_candidate_passages(c, passages, max_candidates=4)
            c_val = _typed_values(c)
            context_values = [_typed_values(p) for p in candidates]
            
            # Numeric rule (original rule, Fix 2 reverted)
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
                
            c_scores = [get_score(p, c) for p in candidates]
            
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
                "candidates": candidates,
                "scores": {
                    "entailment": winning_scores.entailment,
                    "neutral": winning_scores.neutral,
                    "contradiction": winning_scores.contradiction,
                },
                "all_scores": [vars(cs) for cs in c_scores],
            })
            
        traces.append({
            "id": item_id,
            "task": item["task"],
            "quality": item["quality"],
            "gold_spans": item.get("gold_spans", []),
            "claims": re_claims,
            "answer": item["answer"],
            "context": item["context"],
            "inference_seconds": 0.0,
        })
        
    by_id = {str(t["id"]): t for t in traces}
    eval_rows = [score_policy(item, by_id[item["id"]], BASELINE) for item in dev_items.values()]
    m = metrics(eval_rows, include_subgroups=False)
    
    # Label types
    label_totals = defaultdict(int)
    label_intercepted = defaultdict(int)
    for item in dev_items.values():
        tid = str(item["id"])
        labels = rag_by_id.get(tid, {}).get("labels", [])
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
        "by_id": by_id,
        "by_type": by_type,
    }

print("Running simulations...")
res_base = run_simulation(use_new_chunking=False, include_fix1=False, is_baseline=True)
res_3 = run_simulation(use_new_chunking=False, include_fix1=False, is_baseline=False)
res_35 = run_simulation(use_new_chunking=True, include_fix1=False, is_baseline=False)
res_31 = run_simulation(use_new_chunking=False, include_fix1=True, is_baseline=False)
res_315 = run_simulation(use_new_chunking=True, include_fix1=True, is_baseline=False)

base_inter = {r["id"] for r in res_base["eval_rows"] if r["gold_error"] and r["spans"]["fully_intercepted"]}
inter_3 = {r["id"] for r in res_3["eval_rows"] if r["gold_error"] and r["spans"]["fully_intercepted"]}
inter_35 = {r["id"] for r in res_35["eval_rows"] if r["gold_error"] and r["spans"]["fully_intercepted"]}
inter_31 = {r["id"] for r in res_31["eval_rows"] if r["gold_error"] and r["spans"]["fully_intercepted"]}
inter_315 = {r["id"] for r in res_315["eval_rows"] if r["gold_error"] and r["spans"]["fully_intercepted"]}

# =========================================================================
# ITEM 1: {3} vs {3}+Fix5 GAINED and LOST
# =========================================================================
print("\n" + "=" * 80)
print("ITEM 1: {3} vs {3}+Fix5 GAINED AND LOST")
print("=" * 80)

gained_3_to_35 = sorted(list(inter_35 - inter_3), key=lambda x: int(x))
lost_3_to_35 = sorted(list(inter_3 - inter_35), key=lambda x: int(x))

print(f"Intercepted in {{3}}: {len(inter_3)}/321")
print(f"Intercepted in {{3}}+Fix5: {len(inter_35)}/321")
print(f"Net change: {len(inter_35) - len(inter_3):+d}")
print(f"GAINED ({len(gained_3_to_35)} answers): {gained_3_to_35}")
print(f"LOST ({len(lost_3_to_35)} answers): {lost_3_to_35}")

print("\n--- GAINED Answers Details ---")
for aid in gained_3_to_35:
    item = dev_items[aid]
    labels = rag_by_id.get(aid, {}).get("labels", [])
    l_types = [lbl["label_type"] for lbl in labels]
    t3 = res_3["by_id"][aid]
    t35 = res_35["by_id"][aid]
    print(f"\nGained ID {aid} (Task: {item['task']}, Labels: {l_types}):")
    for ci, (c3, c35) in enumerate(zip(t3["claims"], t35["claims"])):
        if c3["verdict"] != c35["verdict"]:
            print(f"  Claim {ci}: {repr(c3['text'][:80])}")
            print(f"    Verdict before chunking: {c3['verdict']} -> after chunking: {c35['verdict']}")
            print(f"    Scores before: E={c3['scores']['entailment']:.4f}, C={c3['scores']['contradiction']:.4f}")
            print(f"    Scores after : E={c35['scores']['entailment']:.4f}, C={c35['scores']['contradiction']:.4f}")

print("\n--- LOST Answers Details ---")
for aid in lost_3_to_35:
    item = dev_items[aid]
    labels = rag_by_id.get(aid, {}).get("labels", [])
    l_types = [lbl["label_type"] for lbl in labels]
    t3 = res_3["by_id"][aid]
    t35 = res_35["by_id"][aid]
    print(f"\nLost ID {aid} (Task: {item['task']}, Labels: {l_types}):")
    for ci, (c3, c35) in enumerate(zip(t3["claims"], t35["claims"])):
        if c3["verdict"] != c35["verdict"]:
            print(f"  Claim {ci}: {repr(c3['text'][:80])}")
            print(f"    Verdict before chunking: {c3['verdict']} -> after chunking: {c35['verdict']}")
            print(f"    Scores before: E={c3['scores']['entailment']:.4f}, C={c3['scores']['contradiction']:.4f}")
            print(f"    Scores after : E={c35['scores']['entailment']:.4f}, C={c35['scores']['contradiction']:.4f}")

# =========================================================================
# ITEM 2: 5 CLEAN ANSWERS NEWLY ALTERED BY FIX 5 (381 vs 376)
# =========================================================================
print("\n" + "=" * 80)
print("ITEM 2: 5 CLEAN ANSWERS NEWLY ALTERED BY FIX 5 (381 vs 376)")
print("=" * 80)

clean_altered_3 = {r["id"] for r in res_3["eval_rows"] if not r["gold_error"] and r["changed"]}
clean_altered_35 = {r["id"] for r in res_35["eval_rows"] if not r["gold_error"] and r["changed"]}

newly_altered = sorted(list(clean_altered_35 - clean_altered_3), key=lambda x: int(x))
print(f"Clean altered in {{3}}: {len(clean_altered_3)}/399")
print(f"Clean altered in {{3}}+Fix5: {len(clean_altered_35)}/399")
print(f"Newly altered clean IDs ({len(newly_altered)}): {newly_altered}")

for aid in newly_altered:
    item = dev_items[aid]
    t3 = res_3["by_id"][aid]
    t35 = res_35["by_id"][aid]
    print(f"\n=======================================================")
    print(f"CLEAN ANSWER ID: {aid} (Task: {item['task']})")
    print(f"Full Answer: {item['answer']}")
    print(f"=======================================================")
    for ci, (c3, c35) in enumerate(zip(t3["claims"], t35["claims"])):
        if c3["verdict"] != c35["verdict"]:
            print(f"\n>>> Claim {ci} flipped: {repr(c3['text'])}")
            print(f"    Verdict: {c3['verdict']} (before) -> {c35['verdict']} (after)")
            print(f"    Winning scores before: {c3['scores']}")
            print(f"    Candidates BEFORE chunking ({len(c3['candidates'])}):")
            for pi, p in enumerate(c3["candidates"]):
                sc = c3["all_scores"][pi]
                print(f"      [P_before {pi}]: E={sc['entailment']:.4f}, N={sc['neutral']:.4f}, C={sc['contradiction']:.4f} | {repr(p)}")
            print(f"    Winning scores after: {c35['scores']}")
            print(f"    Candidates AFTER chunking ({len(c35['candidates'])}):")
            for pi, p in enumerate(c35["candidates"]):
                sc = c35["all_scores"][pi]
                print(f"      [P_after {pi}]: E={sc['entailment']:.4f}, N={sc['neutral']:.4f}, C={sc['contradiction']:.4f} | {repr(p)}")

# =========================================================================
# ITEM 3: REPLAY MATRIX (NO MODEL)
# =========================================================================
print("\n" + "=" * 80)
print("ITEM 3: REPLAY MATRIX (NO MODEL)")
print("=" * 80)

matrix_configs = [
    ("Baseline", res_base, base_inter),
    ("{3}", res_3, inter_3),
    ("{3,5}", res_35, inter_35),
    ("{3,1}", res_31, inter_31),
    ("{3,1,5}", res_315, inter_315),
]

print(f"{'Config':<10} | {'Clean Altered':<20} | {'Intercepted':<20} | {'Char Prec':<10} | {'Gained vs Base':<18} | {'Lost vs Base'}")
print("-" * 105)

for name, r, inter_set in matrix_configs:
    m = r["metrics"]
    ca = f"{m['false_alterations']}/{m['clean']} ({m['false_alteration_rate']*100:.2f}%)"
    ei = f"{m['fully_intercepted']}/{m['erroneous']} ({m['fully_intercepted_rate']*100:.2f}%)"
    cp = f"{m['character_precision']:.4f}"
    gained = sorted(list(inter_set - base_inter), key=lambda x: int(x))
    lost = sorted(list(base_inter - inter_set), key=lambda x: int(x))
    g_str = f"+{len(gained)} {gained}" if gained else "0 []"
    l_str = f"-{len(lost)} {lost}" if lost else "0 []"
    print(f"{name:<10} | {ca:<20} | {ei:<20} | {cp:<10} | {g_str:<18} | {l_str}")

print("\n--- Label-Type Interception ---")
for name, r, _ in matrix_configs:
    print(f"\n{name}:")
    for lt, val in r["by_type"].items():
        print(f"  {lt:24}: {val}")

# =========================================================================
# ITEM 4: VALIDATION SPLIT ENUMERATION (DO NOT FILL)
# =========================================================================
print("\n" + "=" * 80)
print("ITEM 4: VALIDATION SPLIT ENUMERATION (HEAD CODE, DO NOT FILL)")
print("=" * 80)

val_items = {item["id"]: item for item in selected_items(manifest, responses, "validation")}
print(f"Total validation responses: {len(val_items)}")

val_all_pairs = set()
val_cached_pairs = set()
val_new_pairs = set()

for item_id, item in val_items.items():
    claims = split_claims(item["answer"], lang=item["lang"])
    passages = decompose_new(item["context"])
    for c in claims:
        candidates = _select_candidate_passages(c, passages, max_candidates=4)
        for p in candidates:
            k = make_key(p, c)
            val_all_pairs.add((p, c))
            # Check if in base_cache or chunk_cache
            if chunk_cache.get(k) is not None or base_cache.get(k) is not None:
                val_cached_pairs.add((p, c))
            else:
                val_new_pairs.add((p, c))

total_val_pairs = len(val_all_pairs)
cached_val_pairs = len(val_cached_pairs)
new_val_pairs = len(val_new_pairs)

# Timing projection using measured 0.42 s/pair
measured_rate = 0.42
proj_sec = new_val_pairs * measured_rate
proj_hr = proj_sec / 3600

print(f"Total unique (passage, claim) pairs: {total_val_pairs}")
print(f"Already cached                     : {cached_val_pairs} ({cached_val_pairs/total_val_pairs*100:.1f}%)")
print(f"New pairs requiring scoring        : {new_val_pairs} ({new_val_pairs/total_val_pairs*100:.1f}%)")
print(f"Measured scoring rate              : {measured_rate:.2f} s/pair")
print(f"Projected time [PROJECTION]        : {proj_sec:.1f} s ({proj_hr:.2f} hours)")
