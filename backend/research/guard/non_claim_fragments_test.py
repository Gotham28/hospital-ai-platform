"""Unit tests for skipping non-claim fragments during claim extraction."""

import unittest

from backend.research.guard.claims import split_claims


class NonClaimFragmentsTest(unittest.TestCase):
    def test_list_markers_skipped(self):
        answer = "1. Dr. Rao is available on Monday.\n2. The fee is 500.\n3."
        claims = split_claims(answer, lang="en")
        self.assertEqual(
            claims,
            ["Dr. Rao is available on Monday.", "The fee is 500."],
        )

    def test_passage_headers_skipped(self):
        answer = "Passage 1:\nDr. Rao is available.\n(Passage 2)\nThe fee is 500."
        claims = split_claims(answer, lang="en")
        self.assertEqual(
            claims,
            ["Dr. Rao is available.", "The fee is 500."],
        )

    def test_bare_refusals_skipped(self):
        answer = "Unable to answer based on given passages."
        claims = split_claims(answer, lang="en")
        self.assertEqual(claims, [])

        answer2 = "Unable to answer based on the given passages.\nDr. Rao is available."
        claims2 = split_claims(answer2, lang="en")
        self.assertEqual(claims2, ["Dr. Rao is available."])

    def test_conversational_filler_skipped(self):
        answer = "Sure! Dr. Rao is available on Monday."
        claims = split_claims(answer, lang="en")
        self.assertEqual(claims, ["Dr. Rao is available on Monday."])


if __name__ == "__main__":
    unittest.main()
