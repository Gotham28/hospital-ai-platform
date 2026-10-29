import json
from collections import Counter, defaultdict
from pathlib import Path

audit = json.loads(Path("backend/research/results/guard-diagnosis-2026-10-28/stratified_audit_60.json").read_text(encoding="utf-8"))

print("TOTAL SAMPLES:", len(audit))
buckets = ["E_0.5_0.9", "numeric", "high_neutral", "high_contradiction"]

for b in buckets:
    items = [x for x in audit if x["bucket"] == b]
    print(f"\n--- BUCKET: {b} (n={len(items)}) ---")
    cat_counts = Counter(x["category"] for x in items)
    mech_counts = Counter(x["mechanism"] for x in items)
    print("  Category breakdown:", dict(cat_counts))
    print("  Mechanism breakdown:")
    for m, c in sorted(mech_counts.items(), key=lambda t: -t[1]):
        print(f"    {m}: {c}")

print("\n" + "="*70)
print("HIGH CONTRADICTION BUCKET DETAILS (n=15):")
print("="*70)
hc_items = [x for x in audit if x["bucket"] == "high_contradiction"]
for idx, x in enumerate(hc_items, 1):
    print(f"[{idx}] sample_id={x['sample_id']} | task={x['task']} | category={x['category']} | mechanism={x['mechanism']}")
    print(f"     claim: {x['claim']}")
    print(f"     scores: E={x['scores']['entailment']:.4f}, N={x['scores']['neutral']:.4f}, C={x['scores']['contradiction']:.4f}")
    print(f"     reasoning: {x['reasoning']}")
