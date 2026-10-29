import json
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from backend.research.guard.action_policy import BASELINE, should_alter
from backend.research.guard.eval_external import removal_mask
from backend.research.guard import guard
from backend.research.replay.cache import NLICache
from backend.research.replay.scorer import CachedScorer
from backend.research.run_guard_calibration import load_inputs, metrics, score_policy, selected_items

cache_path = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl"
cache = NLICache(cache_path)
scorer = CachedScorer(cache, mode="strict")

manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}

traces_path = repo_root / "backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl"
stored_traces = [json.loads(line) for line in traces_path.read_text(encoding="utf-8").splitlines()]
stored_by_id = {str(t["id"]): t for t in stored_traces}

rag_response_path = repo_root / "backend/research/results/guard-external-2026-10-26/data/rag-response.jsonl"
rag_labels_by_id = {}
with open(rag_response_path, "r", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("labels"):
            rag_labels_by_id[str(r["id"])] = r["labels"]

_, thresholds = guard._thresholds("en")

# 1. First replay baseline with OLD logic or stored reference
# In our replayed baseline (baseline_replay.py):
# 386/399 clean altered, 239/321 intercepted, 0.0729 char precision.
# Let's compute baseline traces from stored_traces but with the 2 exceptions if needed,
# or replay under baseline logic.
# Notice: our baseline replay produced replayed traces for all 720.

# 2. Replay under Fix 1 code
fix1_traces = []
for tid, item in dev_items.items():
    stored = stored_by_id[tid]
    re_claims = []
    for c_idx, stored_c in enumerate(stored["claims"]):
        claim_text = stored_c["text"]
        assessment = scorer.assess(
            claim_text,
            item["context"],
            entailment_threshold=thresholds.entailment,
            contradiction_threshold=thresholds.contradiction,
        )
        re_claims.append({
            "text": claim_text,
            "verdict": assessment.verdict,
            "exact_verdict": assessment.exact_verdict,
            "scores": vars(assessment.scores),
        })
    fix1_traces.append({
        "id": tid,
        "group": stored["group"],
        "task": stored["task"],
        "quality": stored["quality"],
        "gold_spans": stored["gold_spans"],
        "claims": re_claims,
        "answer": item["answer"],
        "inference_seconds": 0.0,
    })

fix1_by_id = {str(t["id"]): t for t in fix1_traces}
eval_rows = [score_policy(item, fix1_by_id[item["id"]], BASELINE) for item in dev_items.values()]
m = metrics(eval_rows, include_subgroups=False)

clean_altered = m["false_alterations"]
clean_total = m["clean"]
err_intercepted = m["fully_intercepted"]
err_total = m["erroneous"]
char_prec = m["character_precision"]

print(f"Clean answers altered     : {clean_altered}/{clean_total} ({m['false_alteration_rate']*100:.2f}%)")
print(f"Erroneous intercepted    : {err_intercepted}/{err_total} ({m['fully_intercepted_rate']*100:.2f}%)")
print(f"Character precision       : {char_prec:.4f} ({char_prec*100:.2f}%)")

# Label-type interception
label_totals = defaultdict(int)
label_intercepted = defaultdict(int)

for item in dev_items.values():
    tid = str(item["id"])
    labels = rag_labels_by_id.get(tid, [])
    if not labels:
        continue
    trace_row = fix1_by_id[tid]
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
    print(f"  {l_type:<25} : {inc}/{tot} ({inc/tot*100:.1f}%)")

# Verdict changes by direction vs replayed baseline
# To compare vs replayed baseline, let's load or compute replayed baseline verdicts
# Replayed baseline has identical verdicts to stored_traces except 12426 claims 2 and 4 (which were contradicted).
baseline_verdicts = {}
for tid, item in dev_items.items():
    stored = stored_by_id[tid]
    for c_idx, c in enumerate(stored["claims"]):
        v = c["verdict"]
        if tid == "12426" and c_idx in (2, 4):
            v = "contradicted"
        baseline_verdicts[(tid, c_idx)] = v

changes_by_dir = defaultdict(int)
changed_claims = []
for tid in dev_items:
    t_fix1 = fix1_by_id[tid]
    for c_idx, c_fix1 in enumerate(t_fix1["claims"]):
        v_base = baseline_verdicts[(tid, c_idx)]
        v_new = c_fix1["verdict"]
        if v_base != v_new:
            direction = f"{v_base} -> {v_new}"
            changes_by_dir[direction] += 1
            changed_claims.append((tid, c_idx, c_fix1["text"], v_base, v_new))

print(f"\nVerdict changes by direction (total {len(changed_claims)} claims):")
for d, count in sorted(changes_by_dir.items()):
    print(f"  {d:<30}: {count}")

# Erroneous answers that lost interception
base_eval_rows = [score_policy(item, stored_by_id[item["id"]], BASELINE) for item in dev_items.values()]
base_intercepted_ids = {r["id"] for r in base_eval_rows if r["gold_error"] and r["spans"]["fully_intercepted"]}
# 12426 was also intercepted in stored
new_intercepted_ids = {r["id"] for r in eval_rows if r["gold_error"] and r["spans"]["fully_intercepted"]}

lost_ids = sorted(list(base_intercepted_ids - new_intercepted_ids), key=lambda x: int(x))
gained_ids = sorted(list(new_intercepted_ids - base_intercepted_ids), key=lambda x: int(x))

print(f"\nErroneous answers that lost interception ({len(lost_ids)}): {lost_ids}")
print(f"Erroneous answers that gained interception ({len(gained_ids)}): {gained_ids}")

# Save report
out_path = Path("C:/Users/Sreehari/.gemini/antigravity-ide/brain/d3e4acec-ffb6-4824-b295-0bcf398df4e3/scratch/fix1_report.json")
out_path.write_text(json.dumps({
    "clean_altered": f"{clean_altered}/{clean_total}",
    "intercepted": f"{err_intercepted}/{err_total}",
    "char_precision": f"{char_prec:.4f}",
    "by_type": {k: f"{label_intercepted[k]}/{label_totals[k]}" for k in label_totals},
    "verdict_changes_by_direction": changes_by_dir,
    "lost_erroneous_ids": lost_ids,
}, indent=2), encoding="utf-8")
