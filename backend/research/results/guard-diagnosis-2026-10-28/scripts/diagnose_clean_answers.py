import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

import json
from collections import Counter, defaultdict
import numpy as np

# Load manifest, traces, sources, responses
ROOT = Path("backend/research")
TRACES_PATH = ROOT / "results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl"
MANIFEST_PATH = ROOT / "results/guard-action-policy-2026-10-27/development-manifest.json"
DATA_DIR = ROOT / "results/guard-external-2026-10-26/data"

from backend.research.run_guard_calibration import load_inputs, selected_items
from backend.research.guard.nli import (
    _decompose_passages,
    _select_candidate_passages,
    _typed_values,
)

print("Loading inputs and traces...")
manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}

traces = [json.loads(line) for line in TRACES_PATH.read_text(encoding="utf-8").splitlines()]
print(f"Total traces: {len(traces)}")

# Identify the 399 clean answers (no annotated error)
clean_traces = [t for t in traces if not t["gold_spans"]]
print(f"Total clean traces (gold_spans empty): {len(clean_traces)}")
assert len(clean_traces) == 399, f"Expected 399, got {len(clean_traces)}"

# Task breakdown of clean answers
tasks = Counter(t["task"] for t in clean_traces)
print(f"Clean answers by task: {dict(tasks)}")

# Diagnosis data structures
by_task = defaultdict(lambda: {
    "total_clean": 0,
    "altered": 0,
    "altered_nli_only": 0,
    "altered_numeric_only": 0,
    "altered_both": 0,
    "flagged_claims_per_answer": [],
    "total_claims": 0,
    "flagged_claims": 0,
    "claim_causes": Counter(),
})

overall = {
    "total_clean": len(clean_traces),
    "altered": 0,
    "altered_nli_only": 0,
    "altered_numeric_only": 0,
    "altered_both": 0,
    "flagged_claims_per_answer": [],
    "total_claims": 0,
    "flagged_claims": 0,
    "claim_causes": Counter(),
}

all_flagged_claims = []

for t in clean_traces:
    tid = t["id"]
    task = t["task"]
    item = dev_items[tid]
    claims = t["claims"]
    
    by_task[task]["total_clean"] += 1
    by_task[task]["total_claims"] += len(claims)
    overall["total_claims"] += len(claims)
    
    ans_has_nli_only = False
    ans_has_numeric_only = False
    ans_has_both = False
    ans_flagged_count = 0
    
    for c_idx, c in enumerate(claims):
        scores = c["scores"]
        exact = c["exact_verdict"]
        verdict = c["verdict"]
        is_flagged = verdict in {"unsupported", "contradicted"}
        
        # Determine cause:
        # NLI alone would flag if: entailment < 0.50 or (contradiction >= 0.30 and contradiction > entailment)
        nli_alone_flags = (scores["entailment"] < 0.50) or (scores["contradiction"] >= 0.30 and scores["contradiction"] > scores["entailment"])
        numeric_alone_flags = exact in {"unsupported", "contradicted"}
        
        if is_flagged:
            ans_flagged_count += 1
            if numeric_alone_flags and not nli_alone_flags:
                cause = "numeric_only"
                ans_has_numeric_only = True
            elif nli_alone_flags and not numeric_alone_flags:
                cause = "nli_only"
                ans_has_nli_only = True
            elif nli_alone_flags and numeric_alone_flags:
                cause = "both"
                ans_has_both = True
            else:
                # Should not happen under baseline
                cause = "other"
            
            by_task[task]["claim_causes"][cause] += 1
            overall["claim_causes"][cause] += 1
            by_task[task]["flagged_claims"] += 1
            overall["flagged_claims"] += 1
            
            all_flagged_claims.append({
                "trace_id": tid,
                "task": task,
                "claim_idx": c_idx,
                "text": c["text"],
                "verdict": verdict,
                "exact_verdict": exact,
                "scores": scores,
                "cause": cause,
                "nli_alone_flags": nli_alone_flags,
                "numeric_alone_flags": numeric_alone_flags,
                "item": item,
            })
            
    by_task[task]["flagged_claims_per_answer"].append(ans_flagged_count)
    overall["flagged_claims_per_answer"].append(ans_flagged_count)
    
    if ans_flagged_count > 0:
        by_task[task]["altered"] += 1
        overall["altered"] += 1
        
        # Categorize answer-level alteration cause:
        if ans_has_numeric_only and not ans_has_nli_only and not ans_has_both:
            by_task[task]["altered_numeric_only"] += 1
            overall["altered_numeric_only"] += 1
        elif ans_has_nli_only and not ans_has_numeric_only and not ans_has_both:
            by_task[task]["altered_nli_only"] += 1
            overall["altered_nli_only"] += 1
        else:
            by_task[task]["altered_both"] += 1
            overall["altered_both"] += 1

print("\n" + "="*80)
print("PART A: FLAGGED CLAIMS AND ANSWERS ALTERED BY CAUSE (Split by Task)")
print("="*80)

for task_name in ["Data2txt", "QA", "Summary", "OVERALL"]:
    st = by_task[task_name] if task_name != "OVERALL" else overall
    n = st["total_clean"]
    alt = st["altered"]
    alt_rate = alt / n if n else 0
    fc = st["flagged_claims_per_answer"]
    mean_fc = np.mean(fc)
    median_fc = np.median(fc)
    p25_fc = np.percentile(fc, 25)
    p75_fc = np.percentile(fc, 75)
    
    print(f"\n--- {task_name} (Total Clean Answers: {n}) ---")
    print(f"Altered Answers: {alt} / {n} ({alt_rate:.2%})")
    print(f"  - Altered by NLI-only claims:     {st['altered_nli_only']:3d} ({st['altered_nli_only']/n:.2%})")
    print(f"  - Altered by Numeric-only claims: {st['altered_numeric_only']:3d} ({st['altered_numeric_only']/n:.2%})")
    print(f"  - Altered by Both (or multiple): {st['altered_both']:3d} ({st['altered_both']/n:.2%})")
    print(f"Flagged Claims per Answer: Mean = {mean_fc:.2f}, Median = {median_fc:.1f}, IQR = [{p25_fc:.0f}, {p75_fc:.0f}], Min = {min(fc)}, Max = {max(fc)}")
    print(f"Total Claims: {st['total_claims']}, Total Flagged Claims: {st['flagged_claims']} ({st['flagged_claims']/st['total_claims']:.2%})")
    print(f"Flagged Claims by Cause:")
    for cause, cnt in st["claim_causes"].most_common():
        print(f"  * {cause:15s}: {cnt:4d} ({cnt/st['flagged_claims']:.2%})")

print("\n" + "="*80)
print("PART B: ENTAILMENT / NEUTRAL / CONTRADICTION SCORE DISTRIBUTIONS")
print("="*80)

ent_scores = np.array([c["scores"]["entailment"] for c in all_flagged_claims])
neu_scores = np.array([c["scores"]["neutral"] for c in all_flagged_claims])
con_scores = np.array([c["scores"]["contradiction"] for c in all_flagged_claims])

def print_dist(name, arr):
    print(f"\n{name} (n={len(arr)}):")
    print(f"  Mean: {np.mean(arr):.4f}, Std: {np.std(arr):.4f}")
    print(f"  Min: {np.min(arr):.4f}, p10: {np.percentile(arr, 10):.4f}, p25: {np.percentile(arr, 25):.4f}, p50: {np.median(arr):.4f}, p75: {np.percentile(arr, 75):.4f}, p90: {np.percentile(arr, 90):.4f}, Max: {np.max(arr):.4f}")
    hist, edges = np.histogram(arr, bins=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0001])
    buckets = [f"[{edges[i]:.1f}-{edges[i+1]:.1f}): {hist[i]}" for i in range(len(hist))]
    print("  Histogram: " + ", ".join(buckets))

print_dist("Entailment Scores of Flagged Claims", ent_scores)
print_dist("Neutral Scores of Flagged Claims", neu_scores)
print_dist("Contradiction Scores of Flagged Claims", con_scores)

# Breakdown of Flagged Claims by Score Profile
high_ent = np.sum(ent_scores >= 0.50)
borderline_ent = np.sum((ent_scores >= 0.30) & (ent_scores < 0.50))
pure_neutral = np.sum((neu_scores >= 0.50) & (con_scores < 0.30))
pure_contradiction = np.sum(con_scores >= 0.50)
moderate_con = np.sum((con_scores >= 0.30) & (con_scores < 0.50))

print("\nFlagged Claim Profile Summary:")
print(f"  Total flagged claims: {len(all_flagged_claims)}")
print(f"  Flagged claims with Entailment >= 0.50 (Overridden by Exact Numeric): {high_ent} ({high_ent/len(all_flagged_claims):.2%})")
print(f"  Flagged claims with Borderline Entailment [0.30, 0.50):             {borderline_ent} ({borderline_ent/len(all_flagged_claims):.2%})")
print(f"  Flagged claims with Neutral >= 0.50 and Contradiction < 0.30:       {pure_neutral} ({pure_neutral/len(all_flagged_claims):.2%})")
print(f"  Flagged claims with Contradiction >= 0.50:                          {pure_contradiction} ({pure_contradiction/len(all_flagged_claims):.2%})")
print(f"  Flagged claims with Contradiction [0.30, 0.50):                     {moderate_con} ({moderate_con/len(all_flagged_claims):.2%})")

# Save detailed json for concrete examples inspection
out_json = Path("backend/research/results/guard-parser-v5-2026-10-28/diagnose_details.json")
# We'll save a subset of rich data for part c
sample_claims = []
for c in all_flagged_claims:
    sample_claims.append({
        "id": c["trace_id"],
        "task": c["task"],
        "text": c["text"],
        "verdict": c["verdict"],
        "exact_verdict": c["exact_verdict"],
        "scores": c["scores"],
        "cause": c["cause"],
        "context": c["item"]["context"],
        "response": c["item"]["answer"],
    })
print(f"\nSaving {len(sample_claims)} flagged claim records for sampling...")
out_json.write_text(json.dumps(sample_claims, indent=2), encoding="utf-8")
print("Saved.")
