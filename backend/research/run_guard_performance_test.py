"""Meaningful evaluator regressions, with no models or network required."""

from __future__ import annotations

import unittest
from pathlib import Path
import tempfile

from backend.research.guard.eval_performance import (
    align_claims, binary_metrics, claim_metrics, interception, latency, summarize,
)


def fixture():
    return dict(answer="The clinic opens Monday. The fee is 999.", ground_truth=dict(
        overall_verdict="contradicted", claims=[
            dict(text="The clinic opens Monday.", verdict="supported"),
            dict(text="The fee is 999.", verdict="contradicted")]))


class EvaluationTests(unittest.TestCase):
    def test_pinned_cache_rejects_revision_drift(self):
        from backend.research.run_guard_performance import MODEL_REVISIONS, _verify_cache
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            for model, revision in MODEL_REVISIONS.items():
                folder = cache / ("models--" + model.replace("/", "--"))
                (folder / "refs").mkdir(parents=True)
                (folder / "snapshots" / revision).mkdir(parents=True)
                (folder / "refs/main").write_text(revision)
            self.assertEqual(_verify_cache(cache), MODEL_REVISIONS)
            next(cache.glob("*/refs/main")).write_text("different-revision")
            with self.assertRaisesRegex(RuntimeError, "drifted"):
                _verify_cache(cache)

    def test_pinned_cache_rejects_missing_snapshot(self):
        from backend.research.run_guard_performance import MODEL_REVISIONS, _verify_cache
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            for model, revision in MODEL_REVISIONS.items():
                folder = cache / ("models--" + model.replace("/", "--"))
                (folder / "refs").mkdir(parents=True)
                (folder / "refs/main").write_text(revision)
            with self.assertRaisesRegex(RuntimeError, "Missing pinned snapshot"):
                _verify_cache(cache)

    def test_wrong_claim_survives_unrelated_redaction(self):
        item = fixture()
        result = dict(final_answer="[FLAG_TEXT] The fee is 999.", changed=True, claims=[
            dict(text="The clinic opens Monday.", verdict="unsupported"),
            dict(text="The fee is 999.", verdict="supported")])
        measured = interception(item, result)
        self.assertTrue(measured["replacement_replay_verified"])
        self.assertFalse(measured["fully_intercepted"])
        self.assertEqual(measured["residual_erroneous_claims"], 1)

    def test_actual_error_redaction(self):
        item = fixture()
        result = dict(final_answer="The clinic opens Monday. [FLAG_TEXT]", claims=[
            dict(text="The clinic opens Monday.", verdict="supported"),
            dict(text="The fee is 999.", verdict="contradicted")])
        self.assertTrue(interception(item, result)["fully_intercepted"])

    def test_partial_abbreviation_redaction_is_not_interception(self):
        item = dict(answer="Dr. Test One charges 999.", ground_truth=dict(
            overall_verdict="contradicted", claims=[dict(text="Dr. Test One charges 999.", verdict="contradicted")]))
        result = dict(final_answer="[FLAG_TEXT] Test One charges 999.", claims=[
            dict(text="Dr.", verdict="unsupported"),
            dict(text="Test One charges 999.", verdict="supported")])
        rows = align_claims(item, result)
        self.assertTrue(rows[0]["complete"])
        self.assertEqual(rows[0]["fragments"], 2)
        self.assertEqual(rows[0]["predicted"], "unsupported")
        self.assertFalse(interception(item, result)["fully_intercepted"])

    def test_substring_alone_is_an_extraction_miss(self):
        item = dict(answer="Dr. Test One charges 999.", ground_truth=dict(
            claims=[dict(text="Dr. Test One charges 999.", verdict="contradicted")]))
        rows = align_claims(item, dict(claims=[dict(text="Dr.", verdict="supported")]))
        self.assertEqual(rows[0]["predicted"], "unmatched")
        scores = claim_metrics(rows)
        self.assertEqual(scores["n"], 1)
        self.assertEqual(scores["accuracy"], 0)
        self.assertEqual(scores["per_class"]["contradicted"]["fn"], 1)

    def test_merged_gold_claims_are_ambiguous(self):
        item = fixture()
        rows = align_claims(item, dict(claims=[dict(text=item["answer"], verdict="supported")]))
        self.assertEqual([r["predicted"] for r in rows], ["unmatched", "unmatched"])

    def test_undeclared_output_edit_cannot_prove_interception(self):
        item = fixture()
        result = dict(claims=[], final_answer="All is well.")
        self.assertFalse(interception(item, result)["replacement_replay_verified"])
        self.assertFalse(interception(item, result)["fully_intercepted"])

    def test_binary_counts_and_undefined_denominators(self):
        metrics = binary_metrics([True, True, False, False], [True, False, True, False])
        self.assertEqual([metrics[x] for x in ("tp", "fp", "fn", "tn")], [1, 1, 1, 1])
        self.assertEqual(metrics["f1"], .5)
        self.assertIsNone(binary_metrics([], [])["precision"])
        self.assertIsNone(binary_metrics([False], [False])["recall"])
        with self.assertRaises(ValueError):
            binary_metrics([True], [])

    def test_latency_interpolation(self):
        self.assertEqual(latency([1., 2., 3., 4.])["p50_seconds"], 2.5)
        self.assertAlmostEqual(latency([1., 2., 3., 4.])["p95_seconds"], 3.85)
        self.assertIsNone(latency([])["p50_seconds"])

    def test_false_alteration_denominator_and_language_gap(self):
        records = []
        for lang, changed in (("en", True), ("ml", False)):
            records.append(dict(lang=lang, split="holdout", gold_overall="supported",
                result=dict(changed=changed, claims=[dict(verdict="unsupported" if changed else "supported")]),
                alignment=[dict(gold="supported", predicted="unsupported" if changed else "supported",
                                complete=True, fragments=1)],
                interception=dict(fully_intercepted=False, residual_erroneous_claims=0),
                gold_final_answer_exact_match=not changed, elapsed_seconds=1.))
        measured = summarize(records)
        self.assertEqual(measured["groups"]["holdout/en"]["false_alteration_rate"], 1.)
        self.assertEqual(measured["groups"]["holdout/ml"]["false_alteration_rate"], 0.)
        self.assertEqual(measured["en_minus_ml"]["holdout"]["false_alteration_rate"], 1.)
        self.assertEqual(measured["groups"]["holdout/all"]["false_alteration_rate"], .5)
        self.assertIsNone(measured["groups"]["tuning/all"]["claims"]["accuracy"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
