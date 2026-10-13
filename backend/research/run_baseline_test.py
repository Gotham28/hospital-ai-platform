"""Offline checks for the G-12 local RARR-style baseline."""

from backend.research.baselines.rarr_style import apply_baseline, attribute_claim


def main() -> None:
    context = [
        "The clinic is open on Monday.",
        "The consultation fee is 500 rupees.",
    ]
    attributed = attribute_claim("The consultation fee is 500 rupees.", context)
    assert attributed.supported
    assert attributed.evidence == context[1]

    result = apply_baseline(
        "The clinic is open on Monday. The clinic offers free parking.",
        context,
        "Answer using the supplied passages.",
        "en",
    )
    assert result["claims"][0]["verdict"] == "supported"
    assert result["claims"][1]["verdict"] == "unsupported"
    assert result["final_answer"] == "The clinic is open on Monday. [FLAG_TEXT]"
    assert result["changed"]
    assert result["conflicts"] == []
    assert result["fact_lock"] == []

    try:
        apply_baseline("Test", context, "Test", "ml")
    except ValueError:
        pass
    else:
        raise AssertionError("Malayalam must be rejected by the English public baseline")

    from backend.research.baselines import apply_guard
    assert apply_guard is apply_baseline

    print("PASS local attribution identifies a supporting passage")
    print("PASS unsupported claims are redacted")
    print("PASS baseline result matches the guard result shape")
    print("PASS English-only limitation is explicit")
    print("PASS apply_guard alias matches the fixed guard interface")
    print("5 passed, 0 failed")


if __name__ == "__main__":
    main()
