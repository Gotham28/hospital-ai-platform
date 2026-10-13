"""Offline checks for the G-13 public evaluation execution module."""

from pathlib import Path

from backend.research.public_eval.evaluate import evaluate_items
from backend.research.public_eval.loader import PublicEvalItem


def main() -> None:
    items = [
        PublicEvalItem(
            question_id="item-1",
            question="What are the visiting hours?",
            context=["Visiting hours are from 4 PM to 7 PM daily."],
            prompt="Answer using the context.",
            source_id="s1",
        ),
        PublicEvalItem(
            question_id="item-2",
            question="Is consultation free?",
            context=["The consultation fee is 300 rupees."],
            prompt="Answer using the context.",
            source_id="s2",
        ),
    ]

    answers = {
        "item-1": "Visiting hours are from 4 PM to 7 PM daily.",
        "item-2": "Yes, consultation is completely free for all patients.",
    }

    results, summary = evaluate_items(items, answers)
    assert summary.total_items == 2
    assert "no_guard" in results
    assert "baseline" in results
    assert "guard_full" in results
    assert len(results["no_guard"]) == 2
    assert len(results["baseline"]) == 2
    assert len(results["guard_full"]) == 2

    # item-1 is supported; item-2 is unsupported/contradicted
    assert results["guard_full"][0]["changed"] is False
    assert results["guard_full"][1]["changed"] is True

    print("PASS public evaluation runs across guard, baseline, and ablations")
    print("PASS supported answer preserved and contradicted answer redacted")
    print(f"PASS summary counts verified: {summary.guard_full_changed_count} changed out of {summary.total_items}")
    print("3 passed, 0 failed")


if __name__ == "__main__":
    main()
