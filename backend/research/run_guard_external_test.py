"""Deterministic regressions for public guard benchmark adapters and metrics."""

import copy
import unittest

from backend.research.guard.eval_external import (
    align_nli, adapt_ragtruth, binary_summary, check_resume, removal_mask,
    language_gaps, paired_gap_intervals, score_spans, summarize_group, whole_verdict,
)


class ExternalTests(unittest.TestCase):
    def test_alignment_requires_test_and_all_labels(self):
        en = [dict(pairID="p1", sentence1="A", sentence2="B", gold_label="neutral")]
        ml = {"test": [dict(premise="അ", hypothesis="ആ", label=1)]}
        self.assertEqual(align_nli(en, ml, expected=1)[0]["gold"], "unsupported")
        with self.assertRaises(ValueError):
            align_nli(en, {"dev": ml["test"]}, expected=1)
        ml["test"][0]["label"] = 0
        with self.assertRaises(ValueError):
            align_nli(en, ml, expected=1)

    def test_duplicate_alignment_ids_rejected(self):
        row = dict(pairID="p1", sentence1="A", sentence2="B", gold_label="neutral")
        ml = {"test": [dict(premise="അ", hypothesis="ആ", label=1)] * 2}
        with self.assertRaises(ValueError):
            align_nli([row, row], ml, expected=2)

    def test_ragtruth_test_only_and_source_join(self):
        source = dict(source_id="s", task_type="Summary", source_info="Evidence here.",
                      prompt="Briefly summarize the following news article:\nEvidence here.\nSummary:")
        response = dict(id="r", source_id="s", split="test", response="A false claim.",
                        labels=[dict(start=2, end=7, text="false", label_type="Evident Conflict")], quality="good")
        item = adapt_ragtruth(response, source)
        self.assertEqual(item["context"], ["Evidence here."])
        self.assertNotIn("Evidence here.", item["instructions"])
        self.assertNotIn("Evident Conflict", str(item["context"]))
        for field, value in (("split", "train"), ("source_id", "wrong")):
            broken = {**response, field: value}
            with self.assertRaises(ValueError):
                adapt_ragtruth(broken, source)
        self.assertEqual(adapt_ragtruth({**response, "split": "train"}, source, required_split="train")["id"], "r")
        with self.assertRaises(ValueError):
            adapt_ragtruth(response, source, required_split="train")
        response["labels"][0]["end"] = 8
        with self.assertRaises(ValueError):
            adapt_ragtruth(response, source)

    def test_qa_passage_boundaries_and_instruction_suffix(self):
        source = dict(source_id="s", task_type="QA", source_info={"question": "Why?", "passages": "passage 1:A\n\npassage 2:B"},
                      prompt="Answer Why? based on passages:\npassage 1:A\n\npassage 2:B\nRefuse if unknown.")
        row = dict(id="r", source_id="s", split="test", response="B", labels=[], quality="good")
        item = adapt_ragtruth(row, source)
        self.assertEqual(item["context"], ["passage 1:A\n\npassage 2:B"])
        self.assertIn("Refuse if unknown.", item["instructions"])
        self.assertNotIn("passage 1:A", item["instructions"])

    def test_span_partial_redaction_is_not_full_interception(self):
        result = dict(claims=[dict(text="Good.", verdict="unsupported"), dict(text="Bad.", verdict="supported")], final_answer="[FLAG_TEXT] Bad.")
        mask = removal_mask("Good. Bad.", result)
        self.assertEqual(score_spans("Good. Bad.", [[6, 10]], mask)["fully_intercepted"], False)
        self.assertEqual(score_spans("abcdef", [[1, 5]], {1, 2})["fully_intercepted"], False)

    def test_replace_all_occurrences_matches_guard(self):
        result = dict(claims=[dict(text="Bad.", verdict="unsupported")], final_answer="[FLAG_TEXT] [FLAG_TEXT]")
        self.assertEqual(removal_mask("Bad. Bad.", result), set(range(4)) | set(range(5, 9)))
        result["final_answer"] = "Bad. [FLAG_TEXT]"
        with self.assertRaises(ValueError):
            removal_mask("Bad. Bad.", result)

    def test_action_override_preserves_detection_verdict(self):
        result = dict(claims=[dict(text="Bad.", verdict="unsupported", altered=False)], final_answer="Bad.")
        self.assertEqual(removal_mask("Bad.", result), set())
        result["claims"][0]["altered"] = True
        result["final_answer"] = "[FLAG_TEXT]"
        self.assertEqual(removal_mask("Bad.", result), set(range(4)))

    def test_span_metrics_no_errors_and_empty_predictions(self):
        m = score_spans("A B", [], {0})
        self.assertEqual(m["fp_chars"], 1)
        self.assertIsNone(m["fully_intercepted"])
        self.assertEqual(score_spans("Bad", [[0, 3]], set())["fn_chars"], 3)

    def test_denominators_and_empty_classes(self):
        m = binary_summary([True, False, False], [True, True, False])
        self.assertEqual((m["tp"], m["fp"], m["fn"], m["tn"]), (1, 1, 0, 1))
        self.assertEqual(m["precision"], .5)
        self.assertIsNone(binary_summary([], [])["precision"])
        self.assertEqual(whole_verdict([]), "unmatched")
        self.assertEqual(whole_verdict([{"verdict": "supported"}, {"verdict": "contradicted"}]), "contradicted")

    def test_resume_rejects_drift_duplicates_and_unknown_ids(self):
        identity = {"models": "a", "data": "b"}
        check_resume(identity, copy.deepcopy(identity), [{"key": "1"}], {"1"})
        for old, rows, expected in (({"models": "x"}, [], {"1"}), (identity, [{"key": "1"}] * 2, {"1"}), (identity, [{"key": "2"}], {"1"})):
            with self.assertRaises(ValueError):
                check_resume(identity, old, rows, expected)

    def test_paired_gap_resamples_corresponding_groups(self):
        rows = [dict(id="1", group="a", gold="supported", predicted="supported", gold_error=False, predicted_error=False),
                dict(id="2", group="a", gold="contradicted", predicted="contradicted", gold_error=True, predicted_error=True)]
        result = paired_gap_intervals(rows, copy.deepcopy(rows), samples=20)
        self.assertEqual(result["ci95"]["three_class_accuracy"], [0.0, 0.0])
        self.assertIn("unavailable", paired_gap_intervals(rows, rows[:1], samples=20))

    def test_character_overlap_includes_whitespace(self):
        self.assertEqual(score_spans("A B", [[0, 3]], {0, 2})["fn_chars"], 1)

    def test_all_failed_rows_remain_visible(self):
        result = summarize_group([dict(group="a", error="inference failed")])
        self.assertEqual((result["selected"], result["completed"], result["failures"]), (1, 0, 1))
        self.assertIsNone(result["detection"]["accuracy"])
        self.assertIn("unavailable", language_gaps([dict(id="a", group="a", error="failed")], []))
        good = dict(id="a", group="a", gold="supported", predicted="supported", gold_error=False, predicted_error=False, elapsed_seconds=0.)
        self.assertIn("unavailable", language_gaps([good], [{**good, "id": "b"}]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
