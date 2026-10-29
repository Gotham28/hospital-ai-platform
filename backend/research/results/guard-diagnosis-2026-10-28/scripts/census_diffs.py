import json
from collections import defaultdict
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(".").resolve()))

from backend.research.guard.guard import _thresholds
from backend.research.replay.cache import NLICache
from backend.research.replay.scorer import CachedScorer
from backend.research.run_guard_calibration import load_inputs, selected_items

manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}
traces_path = Path("backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl")
stored_traces = [json.loads(line) for line in traces_path.read_text(encoding="utf-8").splitlines()]
stored_by_id = {str(t["id"]): t for t in stored_traces}

cache = NLICache("backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl")
scorer = CachedScorer(cache, mode="strict")
_, thresholds = _thresholds("en")

total_claims = 0
count_gt_1e4 = 0
count_gt_001 = 0
count_gt_01 = 0
count_gt_05 = 0

max_overall_diff = 0.0
max_diff_claim = None

claims_above_1e4 = []

for tid, item in dev_items.items():
    stored = stored_by_id[tid]
    task = item["task"]
    for c_idx, stored_c in enumerate(stored["claims"]):
        total_claims += 1
        claim_text = stored_c["text"]
        assessment = scorer.assess(
            claim_text,
            item["context"],
            entailment_threshold=thresholds.entailment,
            contradiction_threshold=thresholds.contradiction,
        )

        de = abs(assessment.scores.entailment - stored_c["scores"]["entailment"])
        dn = abs(assessment.scores.neutral - stored_c["scores"]["neutral"])
        dc = abs(assessment.scores.contradiction - stored_c["scores"]["contradiction"])
        max_c_diff = max(de, dn, dc)

        if max_c_diff > max_overall_diff:
            max_overall_diff = max_c_diff
            max_diff_claim = {
                "answer_id": tid,
                "claim_index": c_idx,
                "task": task,
                "claim_text": claim_text,
                "max_diff": max_c_diff,
                "de": de,
                "dn": dn,
                "dc": dc,
                "stored_verdict": stored_c["verdict"],
                "replayed_verdict": assessment.verdict,
                "stored_scores": stored_c["scores"],
                "replayed_scores": vars(assessment.scores),
            }

        if max_c_diff > 1e-4:
            count_gt_1e4 += 1
            claims_above_1e4.append({
                "answer_id": tid,
                "claim_index": c_idx,
                "task": task,
                "claim_text": claim_text,
                "max_diff": max_c_diff,
                "stored_verdict": stored_c["verdict"],
                "replayed_verdict": assessment.verdict,
                "stored_scores": stored_c["scores"],
                "replayed_scores": vars(assessment.scores),
            })
        if max_c_diff > 0.01:
            count_gt_001 += 1
        if max_c_diff > 0.1:
            count_gt_01 += 1
        if max_c_diff > 0.5:
            count_gt_05 += 1

out_data = {
    "total_claims": total_claims,
    "count_gt_1e4": count_gt_1e4,
    "count_gt_001": count_gt_001,
    "count_gt_01": count_gt_01,
    "count_gt_05": count_gt_05,
    "max_overall_diff": max_overall_diff,
    "max_diff_claim": max_diff_claim,
    "claims_above_1e4": claims_above_1e4,
}

out_path = Path("C:/Users/Sreehari/.gemini/antigravity-ide/brain/d3e4acec-ffb6-4824-b295-0bcf398df4e3/scratch/census_results.json")
out_path.write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")
print("Saved census results to", out_path)
