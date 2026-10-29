import json
from pathlib import Path

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
target_path = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/reference_baseline.json"

census_path = Path("C:/Users/Sreehari/.gemini/antigravity-ide/brain/d3e4acec-ffb6-4824-b295-0bcf398df4e3/scratch/census_results.json")
census = json.loads(census_path.read_text(encoding="utf-8"))

ref_baseline = {
    "source": "replayed_baseline_from_nli_cache",
    "timestamp": "2026-10-29",
    "clean_answers_altered": 386,
    "clean_answers_total": 399,
    "clean_alteration_rate": 386 / 399,
    "erroneous_answers_intercepted": 239,
    "erroneous_answers_total": 321,
    "interception_rate": 239 / 321,
    "interception_floor": 0.6945,
    "char_precision": 0.07294246835150995,
    "interception_by_label_type": {
        "evident_baseless_info": {"intercepted": 198, "total": 248, "rate": 198 / 248},
        "evident_conflict": {"intercepted": 185, "total": 213, "rate": 185 / 213},
        "subtle_baseless_info": {"intercepted": 112, "total": 135, "rate": 112 / 135},
        "subtle_conflict": {"intercepted": 4, "total": 9, "rate": 4 / 9}
    },
    "documented_exceptions": {
        "reason": "Numerical float32 difference between CUDA (RTX 3050 Laptop GPU, torch 2.8.0+cu128) and CPU (torch 2.14.0+cpu). Live CPU scoring matches nli_cache.jsonl 100% (45/45 claims).",
        "total_claims_with_diff_gt_1e4": 45,
        "affected_answers": sorted(list({c["answer_id"] for c in census["claims_above_1e4"]}), key=lambda x: int(x)),
        "claims_with_verdict_difference": [
            {"answer_id": "12426", "claim_index": 2, "stored": "unsupported", "replayed": "contradicted"},
            {"answer_id": "12426", "claim_index": 4, "stored": "unsupported", "replayed": "contradicted"}
        ],
        "metric_impact_on_baseline": "None: answer 12426 is an erroneous answer intercepted under both stored and replayed baselines (386/399 clean altered, 239/321 intercepted, 0.0729 char precision)."
    }
}

target_path.write_text(json.dumps(ref_baseline, indent=2), encoding="utf-8")
print(f"Saved reference baseline to {target_path}")
