"""Reproduce frozen synthetic guard evaluation without paid services.

Use --setup once to cache the existing two models; default inference is offline.
Use --suites to record existing component/regression suites independently.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUTPUT = ROOT / "results" / "guard-performance-2026-10-26"
MODELS = ("MoritzLaurer/mDeBERTa-v3-base-mnli-xnli", "Helsinki-NLP/opus-mt-ml-en")
MODEL_REVISIONS = dict(zip(MODELS, (
    "8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c",
    "ab043b0bded4c755ef79e30a8189085a17fe82ca",
)))


def _save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _offline() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["OMP_NUM_THREADS"] = "4"
    os.environ["MKL_NUM_THREADS"] = "4"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"


def _deny_network(*args, **kwargs):
    raise RuntimeError("Network access is forbidden during guard evaluation")


def _verify_cache(cache_dir: Path | None = None) -> dict[str, str]:
    if cache_dir is None:
        from backend.research.guard.nli import MODEL_CACHE
        cache_dir = MODEL_CACHE
    for model, revision in MODEL_REVISIONS.items():
        folder = cache_dir / ("models--" + model.replace("/", "--"))
        reference = folder / "refs/main"
        if not reference.is_file() or reference.read_text().strip() != revision:
            raise RuntimeError(f"Missing/drifted pinned model reference for {model}; run --setup")
        if not (folder / "snapshots" / revision).is_dir():
            raise RuntimeError(f"Missing pinned snapshot for {model}; run --setup")
    return dict(MODEL_REVISIONS)


def _setup() -> int:
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    # IPv4 succeeds on this Windows network where the default route resets.
    # This affects only this setup process; TLS verification remains enabled.
    import urllib3.util.connection
    urllib3.util.connection.allowed_gai_family = lambda: socket.AF_INET
    from huggingface_hub import HfApi, snapshot_download
    from backend.research.guard.nli import MODEL_CACHE

    revisions = {}
    print("Setup transport: IPv4 HTTPS, certificate verification enabled", flush=True)
    for model in MODELS:
        revision = MODEL_REVISIONS[model]
        info = HfApi().model_info(model, revision=revision, token=False)
        if info.sha != revision:
            raise RuntimeError(f"Unexpected model revision for {model}")
        weights = "*.safetensors" if any(x.rfilename.endswith(".safetensors") for x in info.siblings) else "pytorch_model.bin"
        print(f"Caching {model} revision={revision}", flush=True)
        path = snapshot_download(model, revision=revision, cache_dir=MODEL_CACHE,
                                 token=False, max_workers=2,
                                 allow_patterns=["*.json", "*.model", "*.spm", "*.txt",
                                                 weights])
        if Path(path).name != revision:
            raise RuntimeError("Downloaded snapshot differs from pinned revision")
        # Frozen guard loaders resolve main offline; pin that generated cache
        # reference to the exact snapshot without modifying model/guard source.
        reference = MODEL_CACHE / ("models--" + model.replace("/", "--")) / "refs/main"
        reference.parent.mkdir(parents=True, exist_ok=True)
        reference.write_text(revision, encoding="utf-8")
        revisions[model] = dict(revision=revision, snapshot=path)
        print(f"Cached: {path}", flush=True)
    _save(OUTPUT / "model-downloads.json", revisions)
    _verify_cache()
    return 0


def _suites() -> int:
    _offline()
    from backend.research.guard.nli import MODEL_CACHE
    missing = [model for model in MODELS if not (MODEL_CACHE / (
        "models--" + model.replace("/", "--")) / "refs/main").is_file()]
    failed = False
    for module in ("run_guard_performance_test", "run_guard_claims_test",
                   "run_guard_factlock_test", "run_guard_conflict_test",
                   "run_guard_test", "run_part_d_test", "check_isolation"):
        command = [sys.executable, "-B", "-u", "-m", f"backend.research.{module}"]
        print("$ " + subprocess.list2cmdline(command), flush=True)
        if missing and module in {"run_guard_conflict_test", "run_guard_test", "run_part_d_test"}:
            reason = f"SKIPPED: missing model snapshots: {', '.join(missing)}\n"
            with (OUTPUT / f"{module}.log").open("a", encoding="utf-8") as log:
                log.write("$ " + subprocess.list2cmdline(command) + "\n" + reason)
            print(reason, flush=True)
            failed = True
            continue
        started = time.perf_counter()
        process = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", env={**os.environ,
                                 "PYTHONIOENCODING": "utf-8"})
        raw = ("$ " + subprocess.list2cmdline(command) + "\nSTDOUT:\n" + process.stdout
               + "\nSTDERR:\n" + process.stderr + f"\nExit code: {process.returncode}\n"
               + f"Elapsed seconds: {time.perf_counter() - started:.3f}\n")
        with (OUTPUT / f"{module}.log").open("a", encoding="utf-8") as log:
            log.write(raw)
        print(raw, flush=True)
        failed |= process.returncode != 0
    return int(failed)


def _evaluate() -> int:
    _offline()
    _verify_cache()
    socket.socket.connect = _deny_network
    socket.socket.connect_ex = _deny_network
    socket.create_connection = _deny_network
    started = time.perf_counter()
    import torch
    from backend.research.guard import guard
    from backend.research.guard.conflict import detect_conflicts
    from backend.research.guard.factlock import compare_fact_locks
    from backend.research.guard.eval_performance import (
        align_claims, binary_metrics, divide, interception, summarize,
    )

    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    items = json.loads((ROOT / "fixtures/guard_dev_set.json").read_text(encoding="utf-8"))
    print("Loading local NLI and Malayalam-to-English models (CPU, 4 threads)", flush=True)
    guard._scorer()
    guard._translator()
    cold_load = time.perf_counter() - started
    warm_started = time.perf_counter()
    for lang in ("en", "ml"):
        warm_item = next(item for item in items if item["lang"] == lang)
        guard.apply_guard(warm_item["answer"], warm_item["context"], warm_item["instructions"], lang)
    warmup = time.perf_counter() - warm_started
    records = []
    with (OUTPUT / "cases.jsonl").open("w", encoding="utf-8") as output:
        for index, item in enumerate(items, 1):
            case_started = time.perf_counter()
            result = guard.apply_guard(item["answer"], item["context"], item["instructions"], item["lang"])
            elapsed = time.perf_counter() - case_started
            record = dict(id=item["id"], lang=item["lang"], split=item["split"],
                          gold_overall=item["ground_truth"]["overall_verdict"], result=result,
                          alignment=align_claims(item, result), interception=interception(item, result),
                          gold_final_answer_exact_match=result["final_answer"] == item["ground_truth"]["final_answer"],
                          elapsed_seconds=elapsed)
            records.append(record)
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            output.flush()
            if index % 10 == 0:
                print(f"Guard answers: {index}/{len(items)}", flush=True)

    conflicts = []
    for line in (ROOT / "guard/conflict_cases.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        _, thresholds = guard._thresholds(case["lang"])
        def transform(text):
            return guard._translator().translate(text) if case["lang"] == "ml" and any(
                "\u0d00" <= char <= "\u0d7f" for char in text) else text
        found = detect_conflicts(case["answer"], case["context"], case["instructions"],
                                 case["lang"], guard._scorer(), thresholds, claim_transform=transform)
        expected_types = sorted(set(case["expected_conflicts"]))
        # Frozen labels are type names; reject an unexpected schema rather than guessing.
        if not all(isinstance(x, str) for x in expected_types):
            raise ValueError("Unexpected conflict gold schema")
        predicted_types = sorted({entry["type"] for entry in found})
        conflicts.append(dict(id=case["id"], lang=case["lang"], expected=expected_types,
                              predicted=predicted_types, result=found))
    _save(OUTPUT / "conflicts.json", conflicts)
    conflict_metrics = {}
    for lang in ("all", "en", "ml"):
        selected = [r for r in conflicts if lang == "all" or r["lang"] == lang]
        types = ("instruction_vs_data", "answer_vs_data", "answer_follows_instruction_against_data")
        conflict_metrics[lang] = dict(
            presence=binary_metrics([bool(r["expected"]) for r in selected], [bool(r["predicted"]) for r in selected]),
            type_set_exact_accuracy=divide(sum(r["expected"] == r["predicted"] for r in selected), len(selected)),
            per_type={kind: binary_metrics([kind in r["expected"] for r in selected],
                                           [kind in r["predicted"] for r in selected]) for kind in types})

    locks = []
    for line in (ROOT / "guard/factlock_cases.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        found = compare_fact_locks(case["context"], case["answer"])
        actual = [r["status"] for r in found if r["type"] == case["target_type"]]
        locks.append(dict(id=case["id"], lang=case["lang"], type=case["target_type"],
                          expected=case["expected"], actual=actual, correct=actual == [case["expected"]], result=found))
    _save(OUTPUT / "factlocks.json", locks)
    lock_metrics = {}
    for field, values in (("lang", ("all", "en", "ml")),
                          ("type", sorted({r["type"] for r in locks})),
                          ("expected", sorted({r["expected"] for r in locks}))):
        for value in values:
            selected = [r for r in locks if value == "all" or r[field] == value]
            correct = sum(r["correct"] for r in selected)
            lock_metrics[f"{field}/{value}"] = dict(n=len(selected), correct=correct,
                                                     accuracy=divide(correct, len(selected)))
    summary = summarize(records)
    summary["failures"] = dict(
        claim_verdict_cases=[dict(id=r["id"], lang=r["lang"], split=r["split"],
                                 claims=[c for c in r["alignment"] if c["gold"] != c["predicted"]])
                             for r in records if any(c["gold"] != c["predicted"] for c in r["alignment"])],
        false_alteration_ids=[r["id"] for r in records if r["gold_overall"] == "supported" and r["result"]["changed"]],
        residual_error_ids=[r["id"] for r in records if r["gold_overall"] in {"unsupported", "contradicted"}
                            and not r["interception"]["fully_intercepted"]],
        conflict_type_set_ids=[r["id"] for r in conflicts if r["expected"] != r["predicted"]],
        fact_lock_ids=[r["id"] for r in locks if not r["correct"]],
    )
    summary.update(conflicts=conflict_metrics, fact_lock=lock_metrics,
                   cold_model_load_seconds=cold_load, excluded_warmup_seconds=warmup,
                   total_evaluation_seconds=time.perf_counter() - started)
    _save(OUTPUT / "metrics.json", summary)
    from backend.research.guard.nli import MODEL_CACHE
    paths = [ROOT / "fixtures/guard_dev_set.json", ROOT / "guard/conflict_cases.jsonl",
             ROOT / "guard/factlock_cases.jsonl", ROOT / "guard/thresholds.json"]
    environment = dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                       processor=platform.processor(), cpu_count=os.cpu_count(), device="cpu",
                       torch_threads=torch.get_num_threads(), torch_interop_threads=torch.get_num_interop_threads(),
                       packages={x: importlib.metadata.version(x) for x in ("torch", "transformers", "huggingface-hub",
                                 "sentencepiece", "sacremoses", "protobuf", "numpy")},
                       hashes={str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                       model_revisions=_verify_cache(MODEL_CACHE),
                       command=subprocess.list2cmdline([sys.executable, "-B", "-u", "-m",
                                                         "backend.research.run_guard_performance", *sys.argv[1:]]),
                       sockets_blocked=True, offline=True)
    _save(OUTPUT / "environment.json", environment)
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True)
    (OUTPUT / "pip-freeze.txt").write_text(freeze.stdout + freeze.stderr, encoding="utf-8")
    report = render_report(summary, environment)
    (ROOT / "notes/guard_performance_2026-10-26.md").write_text(report, encoding="utf-8")
    print(report, flush=True)
    print(f"Per-case evidence: {OUTPUT.relative_to(REPO)}", flush=True)
    return 0


def render_report(metrics: dict, environment: dict) -> str:
    def f(value):
        return "undefined" if value is None else f"{value:.3f}"
    lines = ["# Guard performance -- 2026-10-26", "", "## Current-run measurements", "",
             "Frozen synthetic fixtures; existing models, thresholds and guard behavior unchanged.",
             "Holdout is primary. Tuning and all-100 results are descriptive, not independent tests.", "",
             "| Partition | Answers | Gold claims | Claim accuracy | Macro F1 | Detection precision | Recall | F1 | False alterations | Fully intercepted / erroneous |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for partition, group in metrics["groups"].items():
        c, d = group["claims"], group["answer_error_detection"]
        lines.append(f"| {partition} | {group['answers']} | {c['n']} | {f(c['accuracy'])} | {f(c['macro_f1'])} | "
                     f"{f(d['precision'])} | {f(d['recall'])} | {f(d['f1'])} | "
                     f"{group['false_alterations']}/{group['supported_answers']} | "
                     f"{group['fully_intercepted_answers']}/{group['erroneous_answers']} |")
    lines += ["", "## Confusion matrices", "", "Rows are gold; columns are supported, unsupported, contradicted, unmatched."]
    for partition in ("holdout/en", "holdout/ml", "all/en", "all/ml"):
        matrix = metrics["groups"][partition]["claims"]["confusion_matrix"]
        lines += ["", partition, "```json", json.dumps(matrix, indent=2), "```"]
    lines += ["", "## English minus Malayalam gaps", "", "```json", json.dumps(metrics["en_minus_ml"], indent=2), "```",
              "", "## Conflict evaluation (40 cases)", "", "```json", json.dumps(metrics["conflicts"], indent=2), "```",
              "", "## Fact-lock target-status evaluation (40 cases)", "", "```json", json.dumps(metrics["fact_lock"], indent=2), "```",
              "", "## CPU latency", "", f"Cold imports/model load: {metrics['cold_model_load_seconds']:.3f} seconds.",
              f"Excluded warm-up (one answer in each language): {metrics['excluded_warmup_seconds']:.3f} seconds.",
              f"Total evaluation wall time: {metrics['total_evaluation_seconds']:.3f} seconds.", "",
              "| Warm guard answers | n | Mean seconds | p50 seconds | p95 seconds |", "|---|---:|---:|---:|---:|"]
    for partition in ("all/all", "all/en", "all/ml"):
        timing = metrics["groups"][partition]["latency"]
        lines.append(f"| {partition} | {timing['n']} | {f(timing['mean_seconds'])} | {f(timing['p50_seconds'])} | {f(timing['p95_seconds'])} |")
    if "failures" in metrics:
        lines += ["", "## Case failures", "",
                  "All incorrect claim-verdict rows and original outputs are preserved in metrics.json/cases.jsonl.",
                  "```json", json.dumps({key: value if key != "claim_verdict_cases" else [r["id"] for r in value]
                                          for key, value in metrics["failures"].items()}, indent=2), "```"]
    lines += ["", "## Definitions and limitations", "",
              "- Detection positive: any predicted unsupported/contradicted claim. Gold positive: unsupported/contradicted overall answer. Conflicts alone do not count as answer claim detection.",
              "- Claim spans are aligned in original answer text. Complete contiguous fragments are grouped; contradiction takes precedence over unsupported, then supported. Missing/ambiguous claims count as unmatched errors, never disappear from the denominator.",
              "- Full interception requires the declared replacements to reproduce final_answer and remove all original alphanumeric content of every erroneous gold claim. Partial removal is unresolved. Interception is redaction, not factual correction or acceptable patient wording.",
              "- False alteration denominator is gold-supported answers. Unnecessary redaction can damage an otherwise correct answer.",
              "- The old splitter recall suite accepts a substring such as Dr. as a full claim; its 100% does not establish complete extraction or verification accuracy. New metrics disclose fragment groups.",
              "- Conflict presence and exact type sets are labelled; evidence correctness is not. Fact-lock evaluates only the labelled target type/status; extra types are ignored, and entity attribution/completeness is not gold-labelled.",
              "- Fact-lock name aliases cover synthetic Test One--Ten names; they do not prove general transliteration. These 40 cases do not cover number/date targets.",
              "- Frozen synthetic holdout is small and related to tuning data; no new real-world data, native-reader acceptance, clinical safety, production integration, concurrent-load or provider acceptance is established.",
              "- Thresholds were not retuned. Undefined denominators are null in JSON/undefined here. Percentiles use linear interpolation. Socket connections and model downloads were blocked during inference.",
              "- Full per-class precision/recall/F1, residual error counts, alignments and per-case results are in metrics.json/cases.jsonl alongside raw suite outputs and environment metadata.",
              "", "## Focused guard follow-ups (not changed by this task)", "",
              "- Abbreviation fragmentation is source-confirmed at guard/claims.py:7,65 and per-fragment redaction at guard/guard.py:95-110. Case 51 needlessly removes a supported prefix; case 79 leaves an unsupported doctor fragment despite changed=true. Add bilingual abbreviation regressions in a separate algorithm task.",
              "- Malayalam false alterations also occur on whole single-fragment claims (for example cases 80 and 98). Eight of the 20 altered supported Malayalam answers involve fragmentation; twelve do not. Abbreviation repair alone cannot resolve the measured issue.",
              "- guard/nli.py:17 omits English fee/cost/INR price cues from its exact-value parser, while guard/factlock.py has a different price parser. This is a source-level weakness. The current outputs do not retain pivot text or NLI scores, so do not attribute a particular measured failure to translation versus NLI without a dedicated diagnostic task.",
              "- Fact locks are report-only at guard/guard.py:123-124. Cases 80/82/98 show survived values alongside redaction. Any arbitration policy between NLI and fact locks requires a separate decision; matching values alone do not prove a whole claim true.",
              "", "## Runtime identity", "", "```json", json.dumps(environment, indent=2), "```", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--setup", action="store_true")
    mode.add_argument("--suites", action="store_true")
    mode.add_argument("--verify-cache", action="store_true")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # Both streams are preserved, including setup warnings and failed runs.
    class Tee:
        def __init__(self, stream, log):
            self.stream, self.log = stream, log
        def write(self, value):
            self.log.write(value)
            self.log.flush()
            return self.stream.write(value)
        def flush(self):
            self.log.flush()
            self.stream.flush()
        def __getattr__(self, name):
            return getattr(self.stream, name)
    name = "setup" if args.setup else "suites" if args.suites else "cache-check" if args.verify_cache else "performance"
    with (OUTPUT / f"{name}.log").open("a", encoding="utf-8") as log:
        stdout, stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = Tee(stdout, log), Tee(stderr, log)
        try:
            print(f"Run started UTC: {datetime.now(timezone.utc).isoformat()}", flush=True)
            print("$ " + subprocess.list2cmdline([sys.executable, "-B", "-u", "-m",
                                                 "backend.research.run_guard_performance", *sys.argv[1:]]), flush=True)
            try:
                if args.verify_cache:
                    print(json.dumps(_verify_cache(), indent=2), flush=True)
                    code = 0
                else:
                    code = _setup() if args.setup else _suites() if args.suites else _evaluate()
            except Exception:
                import traceback
                traceback.print_exc()
                code = 1
            print(f"Exit code: {code}", flush=True)
            return code
        finally:
            sys.stdout, sys.stderr = stdout, stderr


if __name__ == "__main__":
    raise SystemExit(main())
