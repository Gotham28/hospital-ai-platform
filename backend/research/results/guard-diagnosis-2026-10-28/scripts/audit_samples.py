import json
from pathlib import Path

sample_path = Path("backend/research/results/guard-diagnosis-2026-10-28/stratified_sample_60.json")
samples = json.loads(sample_path.read_text(encoding="utf-8"))

print(f"Loaded {len(samples)} samples.")

# Let's inspect each sample in detail to categorize
results = []
for s in samples:
    sid = s["sample_id"]
    task = s["task"]
    bucket = s["bucket"]
    claim = s["claim"]
    scores = s["scores"]
    exact = s["exact_verdict"]
    active = s["active_passages"]
    ctx = s["all_context"]
    
    # Analyze text matching in full context vs active passages
    full_ctx_str = " ".join(ctx).lower()
    claim_lower = claim.lower()
    
    # We will record data for manual inspection and write helper
    results.append({
        "sample_id": sid,
        "trace_id": s["trace_id"],
        "task": task,
        "bucket": bucket,
        "claim": claim,
        "scores": scores,
        "exact_verdict": exact,
        "active_passages_preview": [p[:100].replace("\n", " ") for p in active],
    })

print(f"Ready to evaluate {len(results)} samples.")
