import json
import sys
from pathlib import Path

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from backend.research.replay.cache import NLICache
from backend.research.run_guard_calibration import load_inputs, selected_items

# Let's import evaluate from sim_fix1
from sim_fix1 import evaluate, dev_items

base_res = evaluate("baseline")
a_res = evaluate("A")

base_inter = {row["id"] for row in base_res["eval_rows"] if row["gold_error"] and row["spans"]["fully_intercepted"]}
a_inter = {row["id"] for row in a_res["eval_rows"] if row["gold_error"] and row["spans"]["fully_intercepted"]}

lost = sorted(list(base_inter - a_inter), key=lambda x: int(x))
gained = sorted(list(a_inter - base_inter), key=lambda x: int(x))

print(f"Base intercepted count: {len(base_inter)}")
print(f"Variant A intercepted count: {len(a_inter)}")
print(f"Lost interception ({len(lost)} answers): {lost}")
print(f"Gained interception ({len(gained)} answers): {gained}")

# For each lost answer, inspect what claims changed verdict
for aid in lost:
    item = dev_items[aid]
    base_t = next(t for t in base_res["replayed_traces"] if str(t["id"]) == aid)
    a_t = next(t for t in a_res["replayed_traces"] if str(t["id"]) == aid)
    print(f"\n==========================================")
    print(f"Answer {aid} (Task: {item['task']}):")
    print(f"Answer text: {repr(item['answer'][:150])}...")
    for ci, (bc, ac) in enumerate(zip(base_t["claims"], a_t["claims"])):
        if bc["verdict"] != ac["verdict"]:
            print(f"  Claim {ci}: {repr(bc['text'])}")
            print(f"    Baseline verdict: {bc['verdict']} -> Variant A verdict: {ac['verdict']}")
            print(f"    Scores: E={ac['scores']['entailment']:.4f}, N={ac['scores']['neutral']:.4f}, C={ac['scores']['contradiction']:.4f}")
