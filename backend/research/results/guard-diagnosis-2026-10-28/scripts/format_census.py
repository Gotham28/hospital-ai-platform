import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
results_path = Path("C:/Users/Sreehari/.gemini/antigravity-ide/brain/d3e4acec-ffb6-4824-b295-0bcf398df4e3/scratch/census_results.json")
data = json.loads(results_path.read_text(encoding="utf-8"))

claims = data["claims_above_1e4"]
grp = defaultdict(list)
for c in claims:
    grp[c["answer_id"]].append(c)

part = sys.argv[1] if len(sys.argv) > 1 else "all"

for aid in sorted(grp.keys(), key=lambda x: int(x)):
    iaid = int(aid)
    if part == "0" and iaid > 3000:
        continue
    if part == "1" and (iaid <= 3000 or iaid > 12430):
        continue
    if part == "2" and iaid <= 12430:
        continue
    task = grp[aid][0]["task"]
    print(f"\n### Answer ID: {aid} (Task: {task})")
    for c in grp[aid]:
        print(f"- **Claim {c['claim_index']}**: {repr(c['claim_text'])}")
        print(f"  - **Stored**: verdict=`{c['stored_verdict']}`, scores=`E={c['stored_scores']['entailment']:.5f}, N={c['stored_scores']['neutral']:.5f}, C={c['stored_scores']['contradiction']:.5f}`")
        print(f"  - **Replayed**: verdict=`{c['replayed_verdict']}`, scores=`E={c['replayed_scores']['entailment']:.5f}, N={c['replayed_scores']['neutral']:.5f}, C={c['replayed_scores']['contradiction']:.5f}`")
        print(f"  - **Max abs diff**: `{c['max_diff']:.5f}` (verdict match: {c['stored_verdict'] == c['replayed_verdict']})")
