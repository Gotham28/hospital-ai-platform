import unittest
from unittest.mock import patch

from backend.research.guard.action_policy import ActionPolicy, BASELINE, should_alter
from backend.research.guard.nli import ClaimAssessment, NLIScores
from backend.research.guard.conflict import ConflictThresholds
from backend.research.guard.guard import GuardOptions, apply_guard_with_options


class ActionPolicyTest(unittest.TestCase):
    def test_baseline_matches_verdict(self):
        scores = NLIScores(.1, .8, .1)
        self.assertFalse(should_alter("supported", scores, None, BASELINE))
        self.assertTrue(should_alter("unsupported", scores, None, BASELINE))
        self.assertTrue(should_alter("contradicted", scores, "contradicted", BASELINE))

    def test_candidate_uses_scores_and_excludes_exact_override(self):
        policy = ActionPolicy("candidate", .7, .8, .2, False)
        self.assertTrue(should_alter("contradicted", NLIScores(.1, .1, .8), None, policy))
        self.assertFalse(should_alter("contradicted", NLIScores(.1, .1, .8), "contradicted", policy))
        self.assertFalse(should_alter("contradicted", NLIScores(.1, .4, .5), None, policy))
        self.assertTrue(should_alter("unsupported", NLIScores(.1, .85, .05), None, policy))
        self.assertFalse(should_alter("unsupported", NLIScores(.3, .85, .05), None, policy))
        self.assertFalse(should_alter("unsupported", NLIScores(.1, .85, .05), "unsupported", policy))

    def test_rejects_unknown_verdict(self):
        with self.assertRaises(ValueError):
            should_alter("unknown", NLIScores(0, 1, 0), None, BASELINE)

    def test_english_action_can_preserve_answer_with_error_verdict(self):
        class FakeScorer:
            def assess(self, *args, **kwargs):
                return ClaimAssessment("unsupported", NLIScores(.1, .7, .2), "Evidence")

        strict = ActionPolicy("strict", .7, .8, .2, False)
        options = GuardOptions(claim_check=True, conflict_surfacing=False, fact_lock=False)
        with patch("backend.research.guard.guard._scorer", return_value=FakeScorer()), \
             patch("backend.research.guard.guard._thresholds", return_value=("direct", ConflictThresholds(.9, .3))), \
             patch("backend.research.guard.guard.ACTIVE_ENGLISH", strict):
            result = apply_guard_with_options("A fact.", ["Evidence"], "", "en", options=options)
        self.assertEqual(result["final_answer"], "A fact.")
        self.assertEqual(result["claims"][0]["verdict"], "unsupported")
        self.assertFalse(result["claims"][0]["altered"])

    def test_malayalam_behavior_ignores_english_action(self):
        class FakeScorer:
            def assess(self, *args, **kwargs):
                return ClaimAssessment("unsupported", NLIScores(.1, .7, .2), "Evidence")

        strict = ActionPolicy("strict", .7, .8, .2, False)
        options = GuardOptions(claim_check=True, conflict_surfacing=False, fact_lock=False)
        with patch("backend.research.guard.guard._scorer", return_value=FakeScorer()), \
             patch("backend.research.guard.guard._thresholds", return_value=("direct", ConflictThresholds(.9, .3))), \
             patch("backend.research.guard.guard.ACTIVE_ENGLISH", strict):
            result = apply_guard_with_options("ഒരു കാര്യം.", ["Evidence"], "", "ml", options=options)
        self.assertEqual(result["final_answer"], "[FLAG_TEXT]")
        self.assertNotIn("altered", result["claims"][0])


if __name__ == "__main__":
    unittest.main()
