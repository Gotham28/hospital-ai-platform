import json
from pathlib import Path

for ver, path in [('v4', 'backend/research/results/guard-action-policy-2026-10-27/development-metrics.json'), 
                  ('v5', 'backend/research/results/guard-parser-v5-2026-10-28/development-metrics.json')]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    res = d.get('results', d)
    print(f"=== {ver} ({path}) ===")
    for p, m in res.items():
        if isinstance(m, dict) and 'clean' in m:
            print(f"{p:15s}: clean altered = {m['false_alterations']:3d} / {m['clean']} ({m['false_alteration_rate']:.2%}) | intercepted = {m['fully_intercepted']:3d} / {m['erroneous']} ({m['fully_intercepted_rate']:.2%})")
