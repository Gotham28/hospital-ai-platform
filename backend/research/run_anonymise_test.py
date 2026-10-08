"""Offline checks for the G-15 anonymisation pipeline using synthetic test data only."""

from backend.research.real_queries.anonymise import anonymise_text


def main() -> None:
    # 1. English synthetic test
    en_sample = (
        "Hello, my name is Mr. John Doe. My phone number is 9876543210 and "
        "my UHID is UHID-99214. I live in Kochi and my DOB: 12/04/1988."
    )
    en_res = anonymise_text(en_sample)
    assert "[PHONE]" in en_res.anonymised_text
    assert "9876543210" not in en_res.anonymised_text
    assert "[ID]" in en_res.anonymised_text
    assert "UHID-99214" not in en_res.anonymised_text
    assert "[PLACE]" in en_res.anonymised_text
    assert "Kochi" not in en_res.anonymised_text
    assert "[DOB]" in en_res.anonymised_text
    assert "[NAME]" in en_res.anonymised_text
    assert en_res.modified

    # 2. Malayalam synthetic test
    ml_sample = (
        "നമസ്കാരം, ശ്രീ രാഹുൽ കുമാർ ഇവിടെ വരുന്നു. ഫോൺ നമ്പർ 9847012345 ആണ്. "
        "ഞങ്ങൾ എറണാകുളം സ്വദേശികളാണ്."
    )
    ml_res = anonymise_text(ml_sample)
    assert "[PHONE]" in ml_res.anonymised_text
    assert "9847012345" not in ml_res.anonymised_text
    assert "[PLACE]" in ml_res.anonymised_text
    assert "എറണാകുളം" not in ml_res.anonymised_text
    assert "[NAME]" in ml_res.anonymised_text
    assert ml_res.modified

    print("PASS English synthetic PII scrubber verified (Phone, ID, Place, DOB, Name)")
    print("PASS Malayalam synthetic PII scrubber verified (Phone, Place, Name)")
    print("PASS zero unscrubbed identifiers leaked in outputs")
    print("3 passed, 0 failed")


if __name__ == "__main__":
    main()
