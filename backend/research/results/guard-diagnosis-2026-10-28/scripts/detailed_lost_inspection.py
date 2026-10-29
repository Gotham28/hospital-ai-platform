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

traces_path = repo_root / "backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl"
stored_by_id = {str(json.loads(line)["id"]): json.loads(line) for line in traces_path.read_text(encoding="utf-8").splitlines()}

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
    stored = stored_by_id[aid]
    
    print("\n" + "=" * 80)
    print(f"ANSWER ID: {aid} (Task: {item['task']}, Quality: {item['quality']})")
    print("=" * 80)
    print(f"Full Answer:\n{item['answer']}\n")
    print(f"Gold Spans (Count: {len(item.get('gold_spans', []))}):")
    for gsi, gs in enumerate(item.get("gold_spans", [])):
        gst = item['answer'][gs[0]:gs[1]]
        print(f"  [{gsi}] text: {repr(gst)} (start={gs[0]}, end={gs[1]})")
    
    print(f"Labels in rag-response: {rag_r.get('labels', [])}")
    
    passages = _decompose_passages(item["context"])
    print(f"\nContext decomposed into {len(passages)} passages.")
    for pi, p in enumerate(passages):
        print(f"  [Passage {pi}]: {repr(p[:120])}...")
        
    claims = split_claims(item["answer"], lang=item["lang"])
    print(f"\nExtracted Claims ({len(claims)}):")
    for ci, c in enumerate(claims):
        candidates = _select_candidate_passages(c, passages, max_candidates=4)
        c_val = _typed_values(c)
        
        # Check span overlap
        overlaps_gold = []
        for gsi, gs in enumerate(item.get("gold_spans", [])):
            gst = item['answer'][gs[0]:gs[1]]
            if gst and (gst in c or c in gst):
                overlaps_gold.append((gsi, gst))
                
        print(f"\n--- Claim {ci}: {repr(c)} ---")
        if overlaps_gold:
            print(f"  ** Overlaps Gold Span: {overlaps_gold} **")
        else:
            print(f"  (Does not directly substring-match gold spans)")
            
        print(f"  Typed values: {c_val}")
        
        for pi, p in enumerate(candidates):
            pv = _typed_values(p)
            k = make_key(p, c)
            entry = cache.get(k)
            if entry:
                print(f"  Candidate {pi} (orig idx in passages?):")
                print(f"    Passage text: {repr(p)}")
                print(f"    E/N/C: E={entry.entailment:.4f}, N={entry.neutral:.4f}, C={entry.contradiction:.4f}")
                print(f"    Passage values: {pv}")
            else:
                print(f"  Candidate {pi}: NOT IN CACHE!")
