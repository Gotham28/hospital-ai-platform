"""Deterministic unit tests for Fix 1: passage selection by entailment before contradiction."""

import unittest
from backend.research.guard.nli import MultilingualNLIScorer, NLIScores, ClaimAssessment


class MockScorer(MultilingualNLIScorer):
    """Subclass that stubs score_pairs to return predetermined scores without loading weights."""

    def __init__(self, scores_to_return: list[NLIScores]) -> None:
        self._stubbed_scores = scores_to_return

    def score_pairs(self, pairs) -> list[NLIScores]:
        return self._stubbed_scores


class PassageSelectionTest(unittest.TestCase):
    def test_entailed_passage_preferred_over_stronger_contradiction(self):
        """Passage with E >= threshold must yield 'supported' even if another passage has higher C."""
        # Passage 0: clearly entails the claim (E=0.92, C=0.02)
        # Passage 1: unrelated passage with high contradiction (E=0.01, C=0.96)
        scores = [
            NLIScores(entailment=0.92, neutral=0.06, contradiction=0.02),
            NLIScores(entailment=0.01, neutral=0.03, contradiction=0.96),
        ]
        scorer = MockScorer(scores)
        passages = [
            "Stuttgart weather report: the minimum temperature will be 58 degrees.",
            "Berlin weather report: the temperature was 20 degrees.",
        ]
        claim = "the minimum temperature is 58 degrees"
        assessment = scorer.assess(
            claim,
            passages,
            entailment_threshold=0.90,
            contradiction_threshold=0.75,
        )
        self.assertEqual(assessment.verdict, "supported")
        self.assertEqual(assessment.scores.entailment, 0.92)
        self.assertEqual(assessment.evidence, passages[0])

    def test_falls_through_to_contradiction_when_entailment_below_threshold(self):
        """When no passage clears entailment threshold, contradiction logic fires."""
        # Passage 0: partial entailment below threshold (E=0.70, C=0.10)
        # Passage 1: strong contradiction (E=0.05, C=0.85)
        scores = [
            NLIScores(entailment=0.70, neutral=0.20, contradiction=0.10),
            NLIScores(entailment=0.05, neutral=0.10, contradiction=0.85),
        ]
        scorer = MockScorer(scores)
        passages = [
            "Weekly weather report mentions variable conditions.",
            "The minimum temperature was strictly reported as 10 degrees, never 58.",
        ]
        claim = "the minimum temperature is 58 degrees"
        assessment = scorer.assess(
            claim,
            passages,
            entailment_threshold=0.90,
            contradiction_threshold=0.75,
        )
        self.assertEqual(assessment.verdict, "contradicted")
        self.assertEqual(assessment.scores.contradiction, 0.85)
        self.assertEqual(assessment.evidence, passages[1])

    def test_falls_through_to_unsupported_when_neither_clears(self):
        """When neither clears thresholds, verdict is unsupported."""
        scores = [
            NLIScores(entailment=0.60, neutral=0.30, contradiction=0.10),
            NLIScores(entailment=0.10, neutral=0.70, contradiction=0.20),
        ]
        scorer = MockScorer(scores)
        passages = [
            "General passage with little detail.",
            "Another passage without relevant figures.",
        ]
        claim = "the minimum temperature is 58 degrees"
        assessment = scorer.assess(
            claim,
            passages,
            entailment_threshold=0.90,
            contradiction_threshold=0.75,
        )
        self.assertEqual(assessment.verdict, "unsupported")


if __name__ == "__main__":
    unittest.main()
