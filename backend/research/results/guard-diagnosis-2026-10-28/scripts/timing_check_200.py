import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

import torch
from backend.research.guard.nli import MultilingualNLIScorer
from backend.research.replay.enumerate_pairs import enumerate_development_pairs

# 1. Thread count
torch.set_num_threads(4)
print("Configured torch.set_num_threads(4)")

# 2. Extract unique pairs
print("Extracting unique (passage, claim) pairs from development traces...")
unique_pairs_dict = {}
for r in enumerate_development_pairs():
    if r.key not in unique_pairs_dict:
        unique_pairs_dict[r.key] = (r.passage, r.claim)

unique_pair_list = list(unique_pairs_dict.values())
total_unique = len(unique_pair_list)
print(f"Total unique pairs: {total_unique}")

# 3. Sample 200 pairs with fixed seed
random.seed(20261028)
sample_200 = random.sample(unique_pair_list, 200)

# Sort by length
sample_200.sort(key=lambda p: len(p[0]) + len(p[1]))

# 4. Initialize scorer
scorer = MultilingualNLIScorer(device="cpu", batch_size=16)

# 5. Warm-up: 1 batch of 16 pairs
print("Running warm-up batch of 16 pairs (discarded)...")
scorer.score_pairs(sample_200[:16])

# 6. Time 200 pairs
print("Timing CPU scoring across 200 pairs (batch_size=16, 4 threads)...")
t0 = time.perf_counter()
scores = scorer.score_pairs(sample_200)
t1 = time.perf_counter()

elapsed = t1 - t0
s_per_pair = elapsed / len(sample_200)

TOTAL_UNIQUE = 22396
proj_sec = TOTAL_UNIQUE * s_per_pair
proj_min = proj_sec / 60.0
proj_hrs = proj_min / 60.0

print("\n" + "="*70)
print("TIMING CHECK RESULTS (200 unique pairs):")
print("="*70)
print(f"Elapsed time (200 pairs)   : {elapsed:.4f} s")
print(f"Seconds per pair           : {s_per_pair:.4f} s/pair")
print(f"Projected for {TOTAL_UNIQUE} pairs : {proj_sec:.1f} s | {proj_min:.2f} min | {proj_hrs:.2f} hours")
print(f"Stop condition (> 3 hours) : {'TRIGGERED' if proj_hrs > 3.0 else 'PASSED (<= 3 hours)'}")

if proj_hrs > 3.0:
    print(f"STOP: Projected total {proj_hrs:.2f} hours exceeds 3 hours limit!")
    sys.exit(1)
else:
    print(f"SUCCESS: Projected time {proj_hrs:.2f} hours is well within 3 hours limit.")
