import json
from collections import defaultdict
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(".").resolve()))

from backend.research.guard.action_policy import BASELINE, should_alter
from backend.research.guard.eval_external import removal_mask, score_spans
from backend.research.guard.guard import _thresholds
from backend.research.run_guard_calibration import load_inputs, metrics, score_policy, selected_items
from backend.research.replay.cache import NLICache
from backend.research.replay.scorer import CachedScorer

manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}
stored_traces = [json.loads(line) for line in Path("backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl").read_text(encoding="utf-8").splitlines()]
cache = NLICache("backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl")
scorer = CachedScorer(cache, mode="strict")
_, thresholds = _thresholds("en")

rag_labels_by_id = {}
rag_path = Path("backend/research/results/guard-external-2026-10-26/data/rag-response.jsonl")
with rag_path.open("r", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("labels"):
            rag_labels_by_id[str(r["id"])] = r["labels"]

replayed_traces = []
for idx, (tid, item) in enumerate(dev_items.items(), 1):
    re_claims = []
    for c_idx, stored_c in enumerate(stored_traces[idx-1]["claims"]):
        assessment = scorer.assess(
            stored_c["text"],
            item["context"],
            entailment_threshold=thresholds.entailment,
            contradiction_threshold=thresholds.contradiction,
        )
        re_claims.append({
            "text": stored_c["text"],
            "verdict": assessment.verdict,
            "exact_verdict": assessment.exact_verdict,
            "scores": vars(assessment.scores),
        })
    replayed_traces.append({
        "id": tid,
        "group": item["group"],
        "task": item["task"],
        "quality": item["quality"],
        "gold_spans": item["gold_spans"],
        "claims": re_claims,
        "inference_seconds": stored_traces[idx-1].get("inference_seconds", 0.0),
    })

replayed_by_id = {str(t["id"]): t for t in replayed_traces}
eval_rows = [score_policy(item, replayed_by_id[item["id"]], BASELINE) for item in dev_items.values()]
base_metrics = metrics(eval_rows, include_subgroups=False)

print("Clean answers altered    :", f"{base_metrics['false_alterations']}/{base_metrics['clean']}")
print("False alteration rate    :", f"{base_metrics['false_alteration_rate']:.6f}")
print("Erroneous intercepted   :", f"{base_metrics['fully_intercepted']}/{base_metrics['erroneous']}")
print("Fully intercepted rate   :", f"{base_metrics['fully_intercepted_rate']:.6f}")
print("Character precision      :", f"{base_metrics['character_precision']:.6f}")

# Label type interception
label_totals = defaultdict(int)
label_intercepted = defaultdict(int)

for item in dev_items.values():
    tid = str(item["id"])
    labels = rag_labels_by_id.get(tid, [])
    if not labels:
        continue
    trace_row = replayed_by_id[tid]
    answer = item["answer"]
    final = answer
    claims = []
    for claim in trace_row["claims"]:
        altered = should_alter(claim["verdict"], SimpleNamespace(**claim["scores"]), claim["exact_verdict"], BASELINE)
        claims.append(dict(text=claim["text"], verdict=claim["verdict"], altered=altered))
        if altered:
            final = final.replace(claim["text"], "[FLAG_TEXT]")
    result = dict(final_answer=final, claims=claims)
    mask = removal_mask(answer, result)

    for lbl in labels:
        l_type = lbl["label_type"]
        span_set = set(range(lbl["start"], lbl["end"]))
        label_totals[l_type] += 1
        if span_set <= mask:
            label_intercepted[l_type] += 1

print("\nInterception by label type:")
for l_type in sorted(label_totals.keys()):
    tot = label_totals[l_type]
    inc = label_intercepted[l_type]
    print(f"  {l_type:<25}: {inc}/{tot} ({inc/tot*100:.1f}%)")
