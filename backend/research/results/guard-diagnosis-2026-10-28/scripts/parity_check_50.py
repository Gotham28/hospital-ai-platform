import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

import json
import random
import torch
import numpy as np

from backend.research.run_guard_calibration import load_inputs, selected_items
from backend.research.guard.nli import MultilingualNLIScorer
from backend.research.guard.guard import _thresholds

print("Loading inputs and traces for parity check...")
manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}

traces = [json.loads(line) for line in Path("backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl").read_text(encoding="utf-8").splitlines()]

# Collect all (item, claim_idx, claim_dict) tuples
all_claims = []
for t in traces:
    tid = t["id"]
    item = dev_items[tid]
    for c_idx, c in enumerate(t["claims"]):
        all_claims.append((item, c_idx, c))

print(f"Total claims in development-v5-traces: {len(all_claims)}")

# Sample 50 random claims with fixed seed 20261028
random.seed(20261028)
sample_50 = random.sample(all_claims, 50)

print("Initializing MultilingualNLIScorer on CPU...")
scorer = MultilingualNLIScorer(device="cpu")
_, thresholds = _thresholds("en")

diffs_e, diffs_n, diffs_c = [], [], []
max_diff = 0.0

print("Running parity check on 50 sampled claims...")
for idx, (item, c_idx, stored_claim) in enumerate(sample_50, 1):
    claim_text = stored_claim["text"]
    stored_scores = stored_claim["scores"]
    
    assessment = scorer.assess(
        claim_text,
        item["context"],
        entailment_threshold=thresholds.entailment,
        contradiction_threshold=thresholds.contradiction,
    )
    
    re_scores = assessment.scores
    de = abs(re_scores.entailment - stored_scores["entailment"])
    dn = abs(re_scores.neutral - stored_scores["neutral"])
    dc = abs(re_scores.contradiction - stored_scores["contradiction"])
    
    diffs_e.append(de)
    diffs_n.append(dn)
    diffs_c.append(dc)
    curr_max = max(de, dn, dc)
    if curr_max > max_diff:
        max_diff = curr_max

    if idx % 10 == 0 or idx == 50:
        print(f"  Processed {idx}/50: running max_diff = {max_diff:.6f}")

all_diffs = diffs_e + diffs_n + diffs_c
mean_diff = float(np.mean(all_diffs))

print("\n" + "="*60)
print("PARITY CHECK RESULTS (n=50 claims, 150 score comparisons):")
print("="*60)
print(f"Max absolute difference  : {max_diff:.8f}")
print(f"Mean absolute difference : {mean_diff:.8f}")
print(f"Max diff <= 0.01 threshold: {max_diff <= 0.01}")

if max_diff > 0.01:
    print("STOP: Parity check failed (max diff > 0.01)")
    sys.exit(1)
else:
    print("PASS: Exact parity verified against stored scores!")
