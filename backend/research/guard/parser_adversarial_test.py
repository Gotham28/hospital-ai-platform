"""Adversarial synthetic tests for guard parser, time, price, and sentence splitting."""

from __future__ import annotations

import unittest

from backend.research.guard.claims import split_claims
from backend.research.guard.factlock import compare_fact_locks, _extract
from backend.research.guard.nli import _typed_values


class ParserAdversarialTests(unittest.TestCase):
    def test_sentence_split_batman_v(self):
        text = "Batman v. Superman: Dawn of Justice was released in 2016. It was directed by Zack Snyder."
        claims = split_claims(text, "en")
        # Should NOT split on "v." into a separate fragment
        self.assertNotIn("Batman v.", claims)
        self.assertTrue(any("Batman v. Superman" in c for c in claims))
        self.assertEqual(len(claims), 2)

    def test_sentence_split_titles_and_abbreviations(self):
        text = "Dr. Test One consults on Monday. Mr. Smith and Mrs. Jones visited St. Jude Hospital."
        claims = split_claims(text, "en")
        self.assertNotIn("Dr.", claims)
        self.assertNotIn("Mr.", claims)
        self.assertNotIn("Mrs.", claims)
        self.assertNotIn("St.", claims)
        self.assertTrue(any("Dr. Test One" in c for c in claims))
        self.assertTrue(any("St. Jude Hospital" in c for c in claims))

    def test_sentence_split_citations_and_latin(self):
        text = "The study in the U.S. confirmed efficacy, e.g. for fever. Apple Inc. funded the trial."
        claims = split_claims(text, "en")
        self.assertNotIn("e.g.", claims)
        self.assertNotIn("U.S.", claims)
        self.assertTrue(any("U.S." in c for c in claims))
        self.assertTrue(any("Apple Inc." in c for c in claims))

    def test_sentence_split_malayalam_title(self):
        text = "ഡോ. ടെസ്റ്റ് വൺ തിങ്കളാഴ്ച ലഭ്യമാണ്. ഫീസ് 400 രൂപയാണ്."
        claims = split_claims(text, "ml")
        self.assertNotIn("ഡോ.", claims)
        self.assertTrue(any("ഡോ. ടെസ്റ്റ് വൺ" in c for c in claims))
        self.assertEqual(len(claims), 2)

    def test_time_canonicalization_single_digit_minute(self):
        locks_short = _extract("The clinic opens at 11:0.")
        locks_full = _extract("The clinic opens at 11:00.")
        time_short = [l for l in locks_short if l.type == "time"]
        time_full = [l for l in locks_full if l.type == "time"]
        self.assertEqual(len(time_short), 1)
        self.assertEqual(len(time_full), 1)
        self.assertEqual(time_short[0].value, "11:00")
        self.assertEqual(time_full[0].value, "11:00")

    def test_time_canonicalization_22_0_and_9_0(self):
        locks = _extract("Open from 9:0 to 22:0 on weekdays.")
        times = sorted(l.value for l in locks if l.type == "time")
        self.assertEqual(times, ["09:00", "22:00"])

    def test_time_factlock_preserved_across_formats(self):
        context = ["Hours: Sunday 11:0-22:0."]
        answer = "We are open on Sunday from 11:00 to 22:00."
        results = compare_fact_locks(context, answer)
        time_results = [r for r in results if r["type"] == "time"]
        self.assertTrue(len(time_results) >= 2)
        for r in time_results:
            self.assertEqual(r["status"], "survived")

    def test_ratio_not_treated_as_time(self):
        locks = _extract("The mixing ratio is 3:1 for the solution.")
        times = [l for l in locks if l.type == "time"]
        self.assertEqual(len(times), 0)
        nli_ratio = _typed_values("The ratio is 3:1, not a time.")
        self.assertEqual(nli_ratio["time"], set())

    def test_nli_colon_overmatching_avoided(self):
        # Colon in non-time context should NOT classify nearby numbers as time
        values = _typed_values("Batman v Superman: Dawn of Justice had 2 main heroes.")
        self.assertEqual(values["time"], set())

        values_note = _typed_values("Note: 5 doctors are on duty.")
        self.assertEqual(values_note["time"], set())

        values_url = _typed_values("Information: https://hospital.org/rates for 3 departments.")
        self.assertEqual(values_url["time"], set())

        values_ratio = _typed_values("The ratio is 3:1, not a time.")
        self.assertEqual(values_ratio["time"], set())

    def test_nli_typed_values_time_normalization(self):
        val_short = _typed_values("Open at 11:0 on Sunday.")
        val_full = _typed_values("Open at 11:00 on Sunday.")
        self.assertEqual(val_short["time"], {"11:00"})
        self.assertEqual(val_full["time"], {"11:00"})

    def test_nli_typed_values_price_and_duration_normalization(self):
        val_price = _typed_values("The consultation fee is 400.00 INR.")
        self.assertEqual(val_price["price"], {"400"})

        val_duration = _typed_values("Take medication for 2.0 days.")
        self.assertEqual(val_duration["duration"], {"2"})

    def test_malayalam_digits_in_factlock_and_nli(self):
        locks = _extract("രാവിലെ ൧൧:൦ ന് ആരംഭിക്കുന്നു.")
        times = [l for l in locks if l.type == "time"]
        self.assertEqual(len(times), 1)
        self.assertEqual(times[0].value, "11:00")

        nli_vals = _typed_values("രാവിലെ ൧൧:൦ ന് ആരംഭിക്കുന്നു.")
        self.assertEqual(nli_vals["time"], {"11:00"})


if __name__ == "__main__":
    unittest.main()
