import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

import json
import random
from collections import defaultdict, Counter
from backend.research.guard.nli import _decompose_passages, _select_candidate_passages, _typed_values

# Load data
data_path = Path("backend/research/results/guard-diagnosis-2026-10-28/diagnose_details.json")
data = json.loads(data_path.read_text(encoding="utf-8"))

def get_bucket(d):
    exact = d['exact_verdict'] in ('unsupported', 'contradicted')
    e = d['scores']['entailment']
    c = d['scores']['contradiction']
    n = d['scores']['neutral']
    if exact:
        return 'numeric'
    elif 0.50 <= e < 0.90:
        return 'E_0.5_0.9'
    elif c >= 0.50:
        return 'high_contradiction'
    elif n >= 0.50 and c < 0.30:
        return 'high_neutral'
    else:
        return 'other'

# Group into 12 strata (3 tasks x 4 buckets)
strata = defaultdict(list)
for item in data:
    b = get_bucket(item)
    if b in ('numeric', 'E_0.5_0.9', 'high_contradiction', 'high_neutral'):
        strata[(item['task'], b)].append(item)

print("Strata population:")
for k, v in sorted(strata.items()):
    print(f"  {k[0]:10s} x {k[1]:20s}: {len(v)} claims")

# Draw 5 per stratum using fixed seed 20261028
random.seed(20261028)
sample = []
for k in sorted(strata.keys()):
    population = strata[k]
    # sort by trace_id and claim_idx for deterministic sampling across platforms
    population.sort(key=lambda x: (x['id'], x['text']))
    chosen = random.sample(population, 5)
    for c in chosen:
        c['stratum_task'] = k[0]
        c['stratum_bucket'] = k[1]
        sample.append(c)

print(f"\nTotal sampled claims: {len(sample)}")

# Prepare rich records with candidate passages
sample_rich = []
for idx, c in enumerate(sample, 1):
    active = _select_candidate_passages(c["text"], _decompose_passages(c["context"]), max_candidates=4)
    claim_val = _typed_values(c["text"])
    passage_vals = [_typed_values(p) for p in active]
    
    sample_rich.append({
        "sample_id": idx,
        "trace_id": c["id"],
        "task": c["stratum_task"],
        "bucket": c["stratum_bucket"],
        "claim": c["text"],
        "verdict": c["verdict"],
        "exact_verdict": c["exact_verdict"],
        "scores": {k: round(v, 4) for k, v in c["scores"].items()},
        "claim_typed_values": {k: list(v) for k, v in claim_val.items() if v},
        "active_passages": active,
        "all_context": c["context"],
        "full_answer": c["response"]
    })

out_path = Path("backend/research/results/guard-diagnosis-2026-10-28/stratified_sample_60.json")
out_path.write_text(json.dumps(sample_rich, indent=2), encoding="utf-8")
print(f"Saved 60 sampled claims to {out_path}")
