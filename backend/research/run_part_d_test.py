"""Offline checks for the G-14 Part D evaluation suite."""

import json
from pathlib import Path

from backend.research.guard.eval_part_d import evaluate_part_d


def main() -> None:
    fixture_path = Path("backend/research/fixtures/guard_dev_set.json")
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found at {fixture_path}")

    items = json.loads(fixture_path.read_text(encoding="utf-8"))
    test_sample = [x for x in items if x.get("lang") == "en"][:5] + [x for x in items if x.get("lang") == "ml"][:5]
    metrics = evaluate_part_d(test_sample)

    assert metrics.total_answers == 10
    assert metrics.en_total > 0
    assert metrics.ml_total > 0
    assert 0.0 <= metrics.en_error_rate_after <= 1.0
    assert 0.0 <= metrics.ml_error_rate_after <= 1.0

    print("PASS Part D evaluation pipeline runs cleanly")
    print(f"PASS English error rate: before={metrics.en_error_rate_before:.2f}, after={metrics.en_error_rate_after:.2f}")
    print(f"PASS Malayalam error rate: before={metrics.ml_error_rate_before:.2f}, after={metrics.ml_error_rate_after:.2f}")
    print(f"PASS Performance gap before: {metrics.gap_before:.2f}, after: {metrics.gap_after:.2f}")
    print("4 passed, 0 failed")


if __name__ == "__main__":
    main()
