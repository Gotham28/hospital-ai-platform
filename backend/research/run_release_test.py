"""Offline checks for the G-16 benchmark release builder."""

from pathlib import Path
import tempfile

from backend.research.release.build_release import build_release_pack


def main() -> None:
    items = [
        {
            "id": 1,
            "split": "tuning",
            "lang": "en",
            "source_type": "synthetic",
            "category": "schedule",
            "phenomenon": "none",
            "test_focus": "doctor schedule",
            "context": ["Dr. Test is available Monday."],
            "instructions": "General query.",
            "answer": "Dr. Test is available Monday.",
            "ground_truth": {"overall_verdict": "supported"},
            "internal_debug_note": "Do not leak this internal field",
        },
        {
            "id": 2,
            "split": "tuning",
            "lang": "en",
            "source_type": "real_unconsented",
            "category": "schedule",
            "phenomenon": "none",
            "context": ["Dr. Test is available Monday."],
            "instructions": "Query.",
            "answer": "Monday.",
            "ground_truth": {"overall_verdict": "supported"},
        },
        {
            "id": 3,
            "split": "tuning",
            "lang": "en",
            "source_type": "synthetic",
            "category": "schedule",
            "phenomenon": "none",
            "context": ["Call 9876543210 for details."],
            "instructions": "Query.",
            "answer": "Call 9876543210.",
            "ground_truth": {"overall_verdict": "supported"},
        },
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        output_file = Path(temp_dir) / "release.jsonl"
        stats = build_release_pack(items, output_file)

        assert stats.total_input == 3
        assert stats.exported_count == 1
        assert stats.rejected_non_synthetic == 1
        assert stats.rejected_privacy_leak == 1

        lines = output_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        exported_line = lines[0]
        assert "internal_debug_note" not in exported_line
        assert '"id": 1' in exported_line
        assert "real_unconsented" not in exported_line

    print("PASS release builder exports public fields correctly")
    print("PASS non-synthetic record blocked from release")
    print("PASS privacy scan blocked phone number leak")
    print("PASS test export verified with zero non-synthetic records")
    print("4 passed, 0 failed")


if __name__ == "__main__":
    main()
