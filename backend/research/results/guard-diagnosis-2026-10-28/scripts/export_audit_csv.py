import csv
import json
from pathlib import Path

audit_path = Path("backend/research/results/guard-diagnosis-2026-10-28/stratified_audit_60.json")
audit = json.loads(audit_path.read_text(encoding="utf-8"))

target_samples = [x for x in audit if x["category"] in {"genuinely_unsupported", "ambiguous"}]

csv_path = Path("backend/research/results/guard-diagnosis-2026-10-28/audit_27_review.csv")

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "sample_id",
        "category",
        "mechanism",
        "claim",
        "entailment",
        "neutral",
        "contradiction",
        "relevant_passage",
        "human_label",
        "human_note",
    ])
    for s in target_samples:
        writer.writerow([
            s["sample_id"],
            s["category"],
            s["mechanism"],
            s["claim"],
            f"{s['scores']['entailment']:.4f}",
            f"{s['scores']['neutral']:.4f}",
            f"{s['scores']['contradiction']:.4f}",
            s.get("primary_passage", ""),
            "",
            "",
        ])

print(f"Exported {len(target_samples)} rows to {csv_path}")
