import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from sim_fix2 import run_eval, dev_items, stored_by_id

base = run_eval(fix1=False, fix2=False)
f2_alone = run_eval(fix1=False, fix2=True)
cum = run_eval(fix1=True, fix2=True)

for name, res in [("Fix 2 ALONE", f2_alone), ("Fix 1 + Fix 2 CUMULATIVE", cum)]:
    print(f"\n==========================================")
    print(f"--- {name} ---")
    changes_by_dir = defaultdict(int)
    changed_claims = []
    for tid in dev_items:
        t_base = next(t for t in base["traces"] if t["id"] == tid)
        t_new = next(t for t in res["traces"] if t["id"] == tid)
        for cidx, (cb, cn) in enumerate(zip(t_base["claims"], t_new["claims"])):
            if cb["verdict"] != cn["verdict"]:
                d = f"{cb['verdict']} -> {cn['verdict']}"
                changes_by_dir[d] += 1
                changed_claims.append((tid, cidx, cb["text"], cb["verdict"], cn["verdict"]))
    print(f"Total claims with changed verdict: {len(changed_claims)}")
    for d, count in sorted(changes_by_dir.items()):
        print(f"  {d:<30}: {count}")

    # Lost erroneous answers
    base_inter = {r["id"] for r in base["eval_rows"] if r["gold_error"] and r["spans"]["fully_intercepted"]}
    new_inter = {r["id"] for r in res["eval_rows"] if r["gold_error"] and r["spans"]["fully_intercepted"]}
    lost = sorted(list(base_inter - new_inter), key=lambda x: int(x))
    gained = sorted(list(new_inter - base_inter), key=lambda x: int(x))
    print(f"Erroneous answers lost interception ({len(lost)}): {lost}")
    print(f"Erroneous answers gained interception ({len(gained)}): {gained}")
