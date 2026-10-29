"""Deterministic unit tests for Fix 2: numeric contradiction requires no matching passage."""

import unittest
from backend.research.guard.nli import MultilingualNLIScorer, NLIScores


class MockScorer(MultilingualNLIScorer):
    """Stub scorer returning uniform neutral scores so exact_verdict takes precedence."""

    def __init__(self) -> None:
        pass

    def score_pairs(self, pairs) -> list[NLIScores]:
        return [NLIScores(entailment=0.5, neutral=0.5, contradiction=0.0) for _ in pairs]


class NumericExactTest(unittest.TestCase):
    def test_no_contradiction_when_one_passage_matches_even_if_another_conflicts(self):
        """If passage 0 conflicts but passage 1 matches the time value, exact contradiction must NOT fire."""
        scorer = MockScorer()
        passages = [
            "Dr. Smith conducts clinic rounds at 4 pm on Saturdays.",
            "Dr. Smith conducts clinic rounds at 1 pm on Wednesdays.",
        ]
        claim = "Dr. Smith conducts clinic rounds at 1 pm on Wednesdays."
        assessment = scorer.assess(
            claim,
            passages,
            entailment_threshold=0.90,
            contradiction_threshold=0.75,
        )
        self.assertNotEqual(assessment.exact_verdict, "contradicted")

    def test_contradiction_when_no_matching_passage_and_at_least_one_conflicts(self):
        """If candidate passages conflict and none matches, exact contradiction fires."""
        scorer = MockScorer()
        passages = [
            "Dr. Smith conducts clinic rounds at 4 pm on Saturdays.",
            "Dr. Smith conducts clinic rounds at 1 pm on Wednesdays.",
        ]
        claim = "Dr. Smith conducts clinic rounds at 6 pm on Wednesdays."
        assessment = scorer.assess(
            claim,
            passages,
            entailment_threshold=0.90,
            contradiction_threshold=0.75,
        )
        self.assertEqual(assessment.exact_verdict, "contradicted")
        self.assertEqual(assessment.verdict, "contradicted")

    def test_unsupported_when_no_values_in_any_candidate_passage(self):
        """Keep rule: when claim has typed values (e.g. price $50) but no passage has any, verdict is unsupported."""
        scorer = MockScorer()
        passages = [
            "General information about clinic appointments and consultations.",
            "Consultation schedules and visiting hours are posted on the notice board.",
        ]
        claim = "The consultation fee is $50."
        assessment = scorer.assess(
            claim,
            passages,
            entailment_threshold=0.90,
            contradiction_threshold=0.75,
        )
        self.assertEqual(assessment.exact_verdict, "unsupported")


if __name__ == "__main__":
    unittest.main()
