"""Offline checks for the G-14 Part D evaluation suite."""

import json
from pathlib import Path
from unittest.mock import patch

from backend.research.guard.eval_part_d import evaluate_part_d


def main() -> None:
    # A supported clause was removed while the erroneous clause survived.
    # The previous changed=true proxy incorrectly counted this as a repair.
    item = dict(lang="en", answer="Open Monday. Fee 999.", context=[], instructions="",
                ground_truth=dict(overall_verdict="contradicted", claims=[
                    dict(text="Open Monday.", verdict="supported"),
                    dict(text="Fee 999.", verdict="contradicted")]))
    with patch("backend.research.guard.eval_part_d.apply_guard_with_options", return_value=dict(
            changed=True, final_answer="[FLAG_TEXT] Fee 999.", claims=[
                dict(text="Open Monday.", verdict="unsupported"),
                dict(text="Fee 999.", verdict="supported")])):
        regression = evaluate_part_d([item])
        assert regression.en_errors_after_guard == 1
    print("PASS unrelated redaction leaves erroneous gold claim unresolved")
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
    print(f"English gold-error answer rate: before={metrics.en_error_rate_before:.2f}, residual after redaction={metrics.en_error_rate_after:.2f}")
    print(f"Malayalam gold-error answer rate: before={metrics.ml_error_rate_before:.2f}, residual after redaction={metrics.ml_error_rate_after:.2f}")
    print(f"PASS Performance gap before: {metrics.gap_before:.2f}, after: {metrics.gap_after:.2f}")
    print(f"False alterations of supported answers: {metrics.false_alteration_count}")
    print("PASS pipeline assertions and wrong-claim-survives regression (not an accuracy threshold)")


if __name__ == "__main__":
    main()
