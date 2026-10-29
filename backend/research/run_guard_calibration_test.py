import unittest
import json
from pathlib import Path
import socket
import tempfile
from unittest.mock import patch

from backend.research.guard.action_policy import ActionPolicy, BASELINE
from backend.research import run_guard_calibration as calibration
from backend.research.run_guard_calibration import metrics, score_policy


class CalibrationTest(unittest.TestCase):
    def tearDown(self):
        calibration.configure_output("v4")

    def test_output_version_routes_v5_and_preflight_away_from_v4(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "guard-action-policy-2026-10-27"
            v5 = root / "guard-parser-v5-2026-10-28"
            legacy.mkdir()
            v4_identity = legacy / "development-v4-identity.json"
            v4_traces = legacy / "development-v4-traces.jsonl"
            v4_identity.write_text("immutable identity", encoding="utf-8")
            v4_traces.write_text("immutable traces", encoding="utf-8")
            with patch.object(calibration, "LEGACY_OUT", legacy), patch.object(calibration, "V5_OUT", v5):
                calibration.configure_output("v5", preflight=True)
                identity, traces = calibration.trace_paths("development")
                self.assertEqual(calibration.OUT, v5 / "preflight-8")
                self.assertEqual(identity, v5 / "preflight-8/development-v5-preflight-identity.json")
                self.assertEqual(traces, v5 / "preflight-8/development-v5-preflight-traces.jsonl")
                self.assertFalse(identity.is_relative_to(legacy))
                calibration.configure_output("v5")
                identity, traces = calibration.trace_paths("development")
                self.assertEqual(calibration.OUT, v5)
                self.assertEqual(identity, v5 / "development-v5-identity.json")
                self.assertEqual(traces, v5 / "development-v5-traces.jsonl")
                calibration.configure_output("v4")
                self.assertEqual(calibration.OUT, legacy)
                self.assertEqual(v4_identity.read_text(encoding="utf-8"), "immutable identity")
                self.assertEqual(v4_traces.read_text(encoding="utf-8"), "immutable traces")

    def test_trace_identity_rejects_missing_and_drifted_files(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(calibration, "OUT", Path(directory)), \
             patch.object(calibration, "expected_trace_identity", return_value={"version": "v3", "device": "cuda"}):
            identity, trace = calibration.trace_paths("development")
            with self.assertRaisesRegex(ValueError, "Missing .* identity"):
                calibration.validate_trace_identity("development")
            trace.write_text("", encoding="utf-8")
            identity.write_text(json.dumps({"version": "old", "device": "cuda"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "identity drift"):
                calibration.validate_trace_identity("development")
            identity.write_text(json.dumps({"version": "v3", "device": "cuda"}), encoding="utf-8")
            self.assertEqual(calibration.validate_trace_identity("development"), {"version": "v3", "device": "cuda"})
            trace.unlink()
            with self.assertRaisesRegex(ValueError, "Missing .* rows"):
                calibration.validate_trace_identity("development")

    def test_replay_and_verification_require_identity(self):
        with patch.object(calibration, "validate_trace_identity", side_effect=ValueError("identity drift")):
            with self.assertRaisesRegex(ValueError, "identity drift"):
                calibration.analyze("development")
            with patch.object(calibration, "load_inputs", return_value=({}, {})), \
                 patch.object(calibration, "selected_items", return_value=[]):
                with self.assertRaisesRegex(ValueError, "identity drift"):
                    calibration.verify_artifacts()

    def test_token_audit_requires_identity(self):
        with patch.object(calibration, "validate_trace_identity", side_effect=ValueError("identity drift")):
            with self.assertRaisesRegex(ValueError, "identity drift"):
                calibration.audit_tokens("development")

    def test_resume_rejects_orphaned_trace_before_loading_model(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(calibration, "OUT", Path(directory)), \
             patch.object(calibration, "load_inputs", return_value=({}, {})), \
             patch.object(calibration, "selected_items", return_value=[]), \
             patch.object(calibration, "expected_trace_identity", return_value={"device": "cuda"}), \
             patch("backend.research.run_guard_performance._verify_cache"), \
             patch.object(socket.socket, "connect"), patch.object(socket.socket, "connect_ex"), \
             patch.object(socket, "create_connection"):
            _, trace = calibration.trace_paths("development")
            trace.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Trace exists without identity"):
                calibration.trace("development", "cuda")

    def test_producer_identity_names_adapter_runner_and_models(self):
        with patch("backend.research.run_guard_performance._verify_cache", return_value={"model": "revision"}):
            identity = calibration.expected_trace_identity("development", "cuda")
        self.assertEqual(identity["trace_version"], "v4")
        self.assertEqual(identity["model_revisions"], {"model": "revision"})
        self.assertIn("backend/research/run_guard_calibration.py", identity["producer_sha256"])
        self.assertIn("backend/research/guard/eval_external.py", identity["producer_sha256"])
        self.assertIn("backend/research/guard/guard.py", identity["producer_sha256"])
        self.assertIn("backend/research/guard/conflict.py", identity["producer_sha256"])
        self.assertIn("backend/research/run_guard_external.py", identity["producer_sha256"])
        self.assertIn("torch_version", identity)
        self.assertIn("transformers_version", identity)

    def test_v5_identity_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(calibration, "OUT", Path(directory)), \
             patch.object(calibration, "OUTPUT_VERSION", "v5"), \
             patch.object(calibration, "TRACE_VERSION", "v5"), \
             patch.object(calibration, "load_inputs", return_value=({}, {})), \
             patch.object(calibration, "selected_items", return_value=[]), \
             patch.object(calibration, "expected_trace_identity", return_value={"trace_version": "v5", "device": "cuda", "producer_sha256": {"runner": "old"}}):
            identity, traces = calibration.trace_paths("development")
            identity.write_text(json.dumps({"trace_version": "v5", "device": "cuda", "producer_sha256": {"runner": "old"}}), encoding="utf-8")
            traces.write_text("", encoding="utf-8")
            calibration.validate_trace_identity("development")
            with patch.object(calibration, "expected_trace_identity", return_value={"trace_version": "v5", "device": "cuda", "producer_sha256": {"runner": "new"}}):
                with self.assertRaisesRegex(ValueError, "identity drift"):
                    calibration.validate_trace_identity("development")

    def test_policy_preserves_detection_but_changes_redaction(self):
        item = dict(id="1", group="g", task="QA", quality="good", answer="A fact.", gold_spans=[[0, 6]])
        trace = dict(claims=[dict(text="A fact.", verdict="unsupported", exact_verdict=None,
                                  scores=dict(entailment=.1, neutral=.7, contradiction=.2))], inference_seconds=.1)
        strict = ActionPolicy("strict", .7, .8, .2, False)
        baseline = score_policy(item, trace, BASELINE)
        candidate = score_policy(item, trace, strict)
        self.assertTrue(baseline["predicted_error"])
        self.assertTrue(candidate["predicted_error"])
        self.assertTrue(baseline["changed"])
        self.assertFalse(candidate["changed"])
        self.assertEqual(metrics([baseline])["fully_intercepted"], 1)
        self.assertEqual(metrics([candidate])["fully_intercepted"], 0)


if __name__ == "__main__":
    unittest.main()
