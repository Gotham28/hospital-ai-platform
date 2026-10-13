"""Run the assembled guard on all 100 synthetic dev-set items."""

from __future__ import annotations

import json
from pathlib import Path
import time

from backend.research.guard.guard import apply_guard

ROOT = Path(__file__).parent
FIXTURE = ROOT / "fixtures" / "guard_dev_set.json"


def main() -> int:
    items = json.loads(FIXTURE.read_text(encoding="utf-8"))
    start = time.perf_counter()
    counts = {"supported": 0, "unsupported": 0, "contradicted": 0}
    changed = 0
    for item in items:
        result = apply_guard(
            item["answer"],
            item["context"],
            item["instructions"],
            item["lang"],
        )
        counts[item["ground_truth"]["overall_verdict"]] += 1
        changed += result["changed"]
    elapsed = time.perf_counter() - start
    print(f"Items processed: {len(items)}")
    print(f"Gold overall verdicts: {counts}")
    print(f"Answers changed: {changed}/{len(items)}")
    print(f"Elapsed seconds: {elapsed:.2f}")
    print(f"Average seconds per answer: {elapsed / len(items):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
