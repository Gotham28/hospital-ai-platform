import sys
from app.services.ml_postprocess import normalise_malayalam

def format_codepoints(text: str) -> str:
    return "".join(f"\\u{ord(c):04X}" for c in text)

def main():
    cases = [
        ("rule_1_chillu_normalisation", "ഡോക്ടര്‍ പ്രിയ", "ഡോക്ടർ പ്രിയ"),
        ("rule_2_abbreviated_title", "ഡോ. പ്രിയ ഇന്ന് ലഭ്യമാണ്", "ഡോക്ടർ പ്രിയ ഇന്ന് ലഭ്യമാണ്"),
        ("rule_3_untranslated_latin_title", "Dr. പ്രിയ ഇന്ന് ലഭ്യമാണ്", "ഡോക്ടർ പ്രിയ ഇന്ന് ലഭ്യമാണ്"),
        ("rule_3_no_match_inside_word", "Drug ഡ്രഗ് Dry ഡ്രൈ", "Drug ഡ്രഗ് Dry ഡ്രൈ"),
        ("empty_and_whitespace", "   ", "   "),
        ("empty_string", "", ""),
        ("english_passthrough", "Dr. Priya is available today.", "Dr. Priya is available today."),
        ("no_rules_match", "പ്രിയ ഇന്ന് ലഭ്യമാണ്", "പ്രിയ ഇന്ന് ലഭ്യമാണ്"),
    ]

    # Additional rule 1 specific chillu cases based on the mappings
    cases.extend([
        ("rule_1_chillu_ra", "\u0D30\u0D4D\u200D", "\u0D7C"),
        ("rule_1_chillu_na", "\u0D28\u0D4D\u200D", "\u0D7B"),
        ("rule_1_chillu_la", "\u0D32\u0D4D\u200D", "\u0D7D"),
        ("rule_1_chillu_lla", "\u0D33\u0D4D\u200D", "\u0D7E"),
        ("rule_1_chillu_nna", "\u0D23\u0D4D\u200D", "\u0D7A"),
    ])

    passed = 0
    failed = 0

    def run_case(name, inp, expected):
        nonlocal passed, failed
        actual = normalise_malayalam(inp)
        if actual == expected:
            print(f"PASS {name}")
            passed += 1
        else:
            print(f"FAIL {name}")
            print(f"  Expected: {expected}")
            print(f"  Actual:   {actual}")
            print(f"  Expected (codepoints): {format_codepoints(expected)}")
            print(f"  Actual (codepoints):   {format_codepoints(actual)}")
            failed += 1

    # Base cases
    for name, inp, expected in cases:
        run_case(name, inp, expected)

    # Idempotent cases over every rule input and every edge case
    for name, inp, expected in cases:
        run_case(f"idempotent_{name}", expected, expected)

    print(f"\n{passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
