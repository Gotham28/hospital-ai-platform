import sys
import json
import time
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
import torch

sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from backend.research.guard.claims import split_claims, _split_sentences
from backend.research.guard.nli import MultilingualNLIScorer, _select_candidate_passages, _typed_values
from backend.research.guard.action_policy import BASELINE, should_alter
from backend.research.guard.eval_external import removal_mask
from backend.research.replay.cache import NLICache, make_key
from backend.research.run_guard_calibration import load_inputs, selected_items, score_policy, metrics

base_cache_path = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl"
base_cache = NLICache(base_cache_path)

new_cache_path = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/nli_cache_chunking.jsonl"

manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}

def decompose_sentence_boundaries(passages: list[str]) -> list[str]:
    chunks = []
    for p in passages:
        sents = _split_sentences(p)
        buf, buf_len = [], 0
        for s in sents:
            s_clean = s.strip()
            if not s_clean:
                continue
            buf.append(s_clean)
            buf_len += len(s_clean)
            if buf_len >= 350:
                chunks.append(" ".join(buf))
                buf, buf_len = [], 0
        if buf:
            chunks.append(" ".join(buf))
    return chunks or passages

# Step 1: Collect pairs needing scoring
print("Collecting unique candidate pairs under sentence-boundary chunking...")
needed_pairs_dict = {}
for item_id, item in dev_items.items():
    claims = split_claims(item["answer"], lang=item["lang"])
    passages = decompose_sentence_boundaries(item["context"])
    for c in claims:
        candidates = _select_candidate_passages(c, passages, max_candidates=4)
        for p in candidates:
            k = make_key(p, c)
            if base_cache.get(k) is None and k not in needed_pairs_dict:
                needed_pairs_dict[k] = (p, c)

new_pairs = list(needed_pairs_dict.values())
print(f"Total new unique pairs to score: {len(new_pairs)}")

# Step 2: Fill new cache file if not already filled
if not new_cache_path.exists() or sum(1 for _ in open(new_cache_path, "r", encoding="utf-8")) < len(new_pairs):
    print(f"Scoring {len(new_pairs)} pairs on CPU (torch threads=8, batch_size=32)...")
    torch.set_num_threads(8)
    scorer = MultilingualNLIScorer(device="cpu", batch_size=32)
    
    t0 = time.perf_counter()
    batch_size = 32
    with open(new_cache_path, "w", encoding="utf-8") as f_out:
        for b_idx in range(0, len(new_pairs), batch_size):
            batch = new_pairs[b_idx:b_idx+batch_size]
            scores = scorer.score_pairs(batch)
            for (p, c), s in zip(batch, scores):
                k = make_key(p, c)
                row = {
                    "key": k,
                    "premise": p,
                    "hypothesis": c,
                    "entailment": s.entailment,
                    "neutral": s.neutral,
                    "contradiction": s.contradiction,
                }
                f_out.write(json.dumps(row, ensure_ascii=False) + "\n")
            if (b_idx // batch_size) % 25 == 0 or b_idx + batch_size >= len(new_pairs):
                elapsed = time.perf_counter() - t0
                pct = min(100.0, (b_idx + len(batch)) / len(new_pairs) * 100)
                print(f"  Progress: {b_idx + len(batch)}/{len(new_pairs)} ({pct:.1f}%) in {elapsed:.1f} s", flush=True)
                f_out.flush()
    print(f"Fill complete in {time.perf_counter() - t0:.1f} s. Saved to {new_cache_path}")
else:
    print(f"New cache file already exists with {sum(1 for _ in open(new_cache_path, 'r', encoding='utf-8'))} entries.")

# Step 3: Combined cache reader
chunk_cache = NLICache(new_cache_path)

def get_score(p: str, c: str):
    k = make_key(p, c)
    val = chunk_cache.get(k)
    if val is not None:
        return val
    return base_cache.get(k)

# Step 4: Replay {3} and {3,1} with sentence-boundary chunking
traces_path = repo_root / "backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl"
stored_by_id = {str(json.loads(line)["id"]): json.loads(line) for line in traces_path.read_text(encoding="utf-8").splitlines()}

rag_response_path = repo_root / "backend/research/results/guard-external-2026-10-26/data/rag-response.jsonl"
rag_labels_by_id = {}
with open(rag_response_path, "r", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("labels"):
            rag_labels_by_id[str(r["id"])] = r["labels"]

def replay_chunking(include_fix1: bool):
    traces = []
    for item_id, item in dev_items.items():
        stored = stored_by_id[item_id]
        raw_claims = split_claims(item["answer"], lang=item["lang"]) # Fix 3
        passages = decompose_sentence_boundaries(item["context"]) # Fix 5
        re_claims = []
        for c in raw_claims:
            candidates = _select_candidate_passages(c, passages, max_candidates=4)
            c_val = _typed_values(c)
            context_values = [_typed_values(p) for p in candidates]
            
            # Numeric check (Fix 2 reverted)
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
                # Fix 1: entailment before contradiction
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
                # Baseline passage selection
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
    by_id = {str(t["id"]): t for t in traces}
    eval_rows = [score_policy(item, by_id[item["id"]], BASELINE) for item in dev_items.values()]
    m = metrics(eval_rows, include_subgroups=False)
    
    # Label types
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
    return m, eval_rows, by_type

from matrix_replay import base_inter

print("\n--- Replay with Sentence-Boundary Chunking (Fix 5) ---")
for name, f1 in [("{3} + Fix 5", False), ("{3,1} + Fix 5", True)]:
    m, eval_rows, by_type = replay_chunking(include_fix1=f1)
    curr_inter = {row["id"] for row in eval_rows if row["gold_error"] and row["spans"]["fully_intercepted"]}
    lost = sorted(list(base_inter - curr_inter), key=lambda x: int(x))
    print(f"\n{name}:")
    print(f"  Clean altered  : {m['false_alterations']}/{m['clean']} ({m['false_alteration_rate']*100:.2f}%)")
    print(f"  Intercepted    : {m['fully_intercepted']}/{m['erroneous']} ({m['fully_intercepted_rate']*100:.2f}%)")
    print(f"  Char precision : {m['character_precision']:.4f}")
    print(f"  Lost IDs ({len(lost)}): {lost}")
    print("  By label type:")
    for lt, val in by_type.items():
        print(f"    {lt:24}: {val}")
