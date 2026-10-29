"""Pinned public test acquisition and offline, resumable frozen-guard evaluation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time
import traceback
import zipfile

from backend.research.guard.eval_external import (
    ERRORS, LABELS, adapt_ragtruth, align_nli, check_resume, cluster_intervals,
    language_gaps, removal_mask, score_spans, summarize_group, whole_verdict,
)

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUTPUT = ROOT / "results/guard-external-2026-10-26"
INDIC_REV = "7092c27872e919f31d0496fb8b9c47bd2cba3f6c"
INDIC_CODE_REV = "4759391f6e349600b75d8505b98471b075aee566"
RAG_REV = "c103204b9ce28d6bbad859304bf30de72b8ed8fe"
XNLI_SHA = "4ba1d5e1afdb7161f0f23c66dc787802ccfa8a25a3ddd3b165a35e50df346ab1"
ML_SHA = "99db2432723cb8e34f99b59e062d85bf1294c1137123b6c299a2fe7d0786aebb"
SOURCES = {
    "xnli.zip": "https://dl.fbaipublicfiles.com/XNLI/XNLI-1.0.zip",
    "indic-ml-test.json": f"https://huggingface.co/datasets/Divyanshu/indicxnli/resolve/{INDIC_REV}/forward/test/xnli_ml.json",
    "indic-generation.txt": f"https://raw.githubusercontent.com/divyanshuaggarwal/IndicXNLI/{INDIC_CODE_REV}/src/make_dataset.py",
    "xnli-loader.txt": "https://huggingface.co/datasets/facebook/xnli/resolve/5ab89245fbc9c1b28514b43b238cdb70f330948e/xnli.py",
    "indic-loader.txt": f"https://huggingface.co/datasets/Divyanshu/indicxnli/resolve/{INDIC_REV}/indicxnli.py",
    "indic-readme.txt": f"https://huggingface.co/datasets/Divyanshu/indicxnli/resolve/{INDIC_REV}/README.md",
    "rag-response.jsonl": f"https://raw.githubusercontent.com/ParticleMedia/RAGTruth/{RAG_REV}/dataset/response.jsonl",
    "rag-source.jsonl": f"https://raw.githubusercontent.com/ParticleMedia/RAGTruth/{RAG_REV}/dataset/source_info.jsonl",
    "rag-readme.txt": f"https://raw.githubusercontent.com/ParticleMedia/RAGTruth/{RAG_REV}/README.md",
    "rag-license.txt": f"https://raw.githubusercontent.com/ParticleMedia/RAGTruth/{RAG_REV}/LICENSE",
    "rag-preparation.txt": f"https://raw.githubusercontent.com/ParticleMedia/RAGTruth/{RAG_REV}/baseline/prepare_dataset.py",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def download() -> None:
    import requests
    import urllib3.util.connection
    # Existing approved setup transport; public HTTPS only, normal TLS validation.
    urllib3.util.connection.allowed_gai_family = lambda: socket.AF_INET
    data = OUTPUT / "data"
    data.mkdir(parents=True, exist_ok=True)
    manifest = dict(indic_revision=INDIC_REV, indic_code_revision=INDIC_CODE_REV,
                    ragtruth_revision=RAG_REV, tls_verification=True, files={})
    for name, url in SOURCES.items():
        destination = data / name
        print(f"GET {url}", flush=True)
        if not destination.exists():
            response = requests.get(url, timeout=(20, 180))
            response.raise_for_status()
            destination.write_bytes(response.content)
        checksum = sha(destination)
        expected = {"xnli.zip": XNLI_SHA, "indic-ml-test.json": ML_SHA}.get(name)
        if expected and checksum != expected:
            raise ValueError(f"Unexpected published data SHA256: {name}")
        manifest["files"][name] = dict(url=url, sha256=checksum, bytes=destination.stat().st_size)
        print(f"  bytes={destination.stat().st_size} sha256={checksum}", flush=True)
    save(OUTPUT / "data-manifest.json", manifest)
    validate()


def load_items() -> tuple[list[dict], list[dict]]:
    manifest = json.loads((OUTPUT / "data-manifest.json").read_text(encoding="utf-8"))
    data = OUTPUT / "data"
    if set(manifest["files"]) != set(SOURCES):
        raise ValueError("Incomplete source manifest")
    for name, entry in manifest["files"].items():
        if entry["url"] != SOURCES[name] or sha(data / name) != entry["sha256"]:
            raise ValueError(f"Dataset/source drift: {name}")
    if sha(data / "xnli.zip") != XNLI_SHA or sha(data / "indic-ml-test.json") != ML_SHA:
        raise ValueError("Published XNLI/IndicXNLI hashes differ")
    with zipfile.ZipFile(data / "xnli.zip") as archive:
        text = archive.read("XNLI-1.0/xnli.test.tsv").decode("utf-8-sig")
    english = [r for r in csv.DictReader(io.StringIO(text), delimiter="\t") if r["language"] == "en"]
    nli = align_nli(english, json.loads((data / "indic-ml-test.json").read_text(encoding="utf-8")))
    sources = {}
    for line in (data / "rag-source.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["source_id"] in sources:
            raise ValueError("Duplicate RAGTruth source IDs")
        sources[row["source_id"]] = row
    responses = [json.loads(line) for line in (data / "rag-response.jsonl").read_text(encoding="utf-8").splitlines()]
    tests = [r for r in responses if r["split"] == "test"]
    if len({r["id"] for r in responses}) != len(responses) or any(r["split"] not in {"test", "train"} for r in responses):
        raise ValueError("Duplicate response IDs or unknown official split")
    rag = [adapt_ragtruth(r, sources[r["source_id"]]) for r in tests]
    train_sources = {r["source_id"] for r in responses if r["split"] == "train"}
    if train_sources & {r["group"] for r in rag}:
        raise ValueError("Official RAGTruth source appears in both train and test")
    return nli, rag


def validate() -> dict:
    from collections import Counter
    nli, rag = load_items()
    summary = dict(nli_pairs_per_language=len(nli), alignment="upstream preserved ordinal; every label checked",
                   nli_labels=dict(Counter(r["gold"] for r in nli)), nli_source_groups=len({r["group"] for r in nli}),
                   ragtruth_test=len(rag), ragtruth_source_groups=len({r["group"] for r in rag}),
                   ragtruth_quality=dict(Counter(r["quality"] for r in rag)),
                   ragtruth_tasks=dict(Counter(r["task"] for r in rag)),
                   ragtruth_error_answers=sum(bool(r["gold_spans"]) for r in rag),
                   annotation_policy="All published spans including implicit_true/due_to_null; all test qualities primary; quality-good sensitivity",
                   context_policy="Published source field intact, original prompt minus its exact evidence block; no new chunking")
    save(OUTPUT / "validation.json", summary)
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def evaluate(args) -> int:
    from backend.research.run_guard_performance import _deny_network, _offline, _verify_cache
    _offline()
    revisions = _verify_cache()
    socket.socket.connect = _deny_network
    socket.socket.connect_ex = _deny_network
    socket.create_connection = _deny_network
    nli, rag = load_items()
    if args.limit:
        nli, rag = nli[:args.limit], rag[:args.limit]
    conditions = args.conditions.split(",")
    work = []
    if args.benchmark in {"nli", "all"}:
        for lang in args.languages.split(","):
            for condition in conditions:
                for item in nli:
                    work.append((f"nli/{lang}/{condition}/{item['id']}", "nli", lang, condition, item))
    if args.benchmark in {"ragtruth", "all"} and "guard" in conditions:
        work += [(f"ragtruth/en/guard/{item['id']}", "ragtruth", "en", "guard", item) for item in rag]
    if not work:
        raise ValueError("No benchmark conditions selected")
    candidate_output = ROOT / "results/guard-action-policy-2026-10-27"
    run = (candidate_output if args.action_candidate else OUTPUT) / args.run_name
    run.mkdir(parents=True, exist_ok=True)
    baseline = json.loads((OUTPUT / "baseline.json").read_text(encoding="utf-8"))
    for name, checksum in baseline["hashes"].items():
        if args.action_candidate and name in {
            "backend/research/guard/guard.py", "backend/research/guard/eval_external.py",
            "backend/research/run_guard_external.py", "backend/research/run_guard_external_test.py",
            "backend/research/guard/claims.py", "backend/research/guard/nli.py",
            "backend/research/guard/factlock.py",
        }:
            continue
        if sha(REPO / name) != checksum:
            raise ValueError(f"Frozen source/prior report drift: {name}")
    if args.action_candidate:
        from backend.research.guard.action_policy import ACTIVE_ENGLISH
        decision = json.loads((candidate_output / "validation-decision.json").read_text(encoding="utf-8"))
        if not decision["passed"] or ACTIVE_ENGLISH.name != decision["selected"]:
            raise ValueError("Candidate must match passed reserved validation")
    source_paths = [Path(__file__), ROOT / "guard/eval_external.py", ROOT / "run_guard_external_test.py",
                    ROOT / "guard/guard.py", ROOT / "guard/action_policy.py",
                    ROOT / "guard/claims.py", ROOT / "guard/nli.py", ROOT / "guard/factlock.py"]
    identity = dict(data_manifest=sha(OUTPUT / "data-manifest.json"), model_revisions=revisions,
                    frozen_hashes=baseline["hashes"], source_hashes={str(p.relative_to(REPO)): sha(p) for p in source_paths},
                    benchmark=args.benchmark, conditions=conditions, languages=args.languages, limit=args.limit,
                    action_candidate=args.action_candidate, device=args.device, threads=4,
                    precision="float32; TF32 disabled",
                    policy="strict-all-test; original intact context; original instruction minus evidence; no-cache; batch1")
    if args.action_candidate:
        identity["candidate_evidence_hashes"] = {
            name: sha(candidate_output / name) for name in
            ("development-manifest.json", "development-selection.json", "validation-decision.json", "validation-metrics.json")
        }
        identity["calibration_source_sha256"] = sha(ROOT / "run_guard_calibration.py")
    identity_path, cases = run / "identity.json", run / "cases.jsonl"
    previous = [json.loads(line) for line in cases.read_text(encoding="utf-8").splitlines()] if cases.exists() else []
    if identity_path.exists():
        check_resume(identity, json.loads(identity_path.read_text(encoding="utf-8")), previous, {w[0] for w in work})
    elif previous:
        raise ValueError("Cannot resume cases without an identity manifest")
    else:
        save(identity_path, identity)
    done = {r["key"] for r in previous}
    started = time.perf_counter()
    import torch
    from backend.research.guard import guard
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable; no silent CPU fallback")
    torch.set_float32_matmul_precision("highest")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    scorer = guard._scorer()
    # Load on CPU first to avoid the frozen scorer constructor's CUDA fp16 cast.
    # Moving float32 tensors directly preserves their original weight values.
    if args.device == "cuda":
        scorer.device = torch.device("cuda")
        scorer._model.to(device=scorer.device, dtype=torch.float32)
    if any(w[2] == "ml" and w[3] == "guard" for w in work):
        translator = guard._translator()
        if args.device == "cuda":
            translator.device = torch.device("cuda")
            translator.model.to(device=translator.device, dtype=torch.float32)
    cold = time.perf_counter() - started
    original_score = scorer.score_pairs
    counters = dict(pairs=0, truncated=0, max_untruncated_tokens=0)
    def measured_pairs(pairs):
        pairs = list(pairs)
        values = original_score(pairs)
        if not all(math.isfinite(v) for row in values for v in (row.entailment, row.neutral, row.contradiction)):
            raise RuntimeError("Non-finite NLI probabilities")
        for premise, hypothesis in pairs:
            count = len(scorer._tokenizer(premise, hypothesis, truncation=False, verbose=False)["input_ids"])
            counters["pairs"] += 1
            counters["truncated"] += count > 512
            counters["max_untruncated_tokens"] = max(counters["max_untruncated_tokens"], count)
        return values
    scorer.score_pairs = measured_pairs
    warm_started = time.perf_counter()
    for lang in sorted({w[2] for w in work}):
        if lang == "ml" and "guard" in conditions:
            guard.apply_guard("ഇത് ഒരു ആശുപത്രിയാണ്.", ["This is a hospital."], "", lang)
        else:
            scorer.score_pairs([("This is evidence.", "This is evidence.")])
    warmup = time.perf_counter() - warm_started
    environment = dict(command=subprocess.list2cmdline([sys.executable, "-B", "-u", "-m", "backend.research.run_guard_external", *sys.argv[1:]]),
                       python=sys.version, platform=platform.platform(), processor=platform.processor(), cpu_count=os.cpu_count(),
                       torch_version=torch.__version__, device=args.device, cuda_build=torch.version.cuda,
                       gpu_name=torch.cuda.get_device_name() if args.device == "cuda" else None,
                       dtype="float32", tf32=False, threads=4, interop_threads=1, offline=True,
                       network_blocked=True, cold_imports_and_load_seconds=cold, existing_rows=len(done), excluded_warmup_seconds=warmup,
                       timing="Uncached serial calls including measurement tokenizer overhead; fixed artificial warmup excluded")
    save(run / f"environment-{time.time_ns()}.json", environment)
    print(f"Loaded models in {cold:.3f}s; completed={len(done)}/{len(work)}; device={args.device}; float32; threads=4; offline", flush=True)
    consecutive_errors = 0
    with cases.open("a", encoding="utf-8") as output:
        for index, (key, benchmark, lang, condition, item) in enumerate(work, 1):
            if key in done:
                continue
            counters.update(pairs=0, truncated=0, max_untruncated_tokens=0)
            case_started = time.perf_counter()
            record = dict(key=key, dataset=benchmark, lang=lang, condition=condition, id=item["id"], group=item["group"])
            try:
                if benchmark == "nli":
                    record["gold"] = item["gold"]
                    record["gold_error"] = item["gold"] in ERRORS
                    if condition == "raw":
                        scores = scorer.score_pairs([(item[f"{lang}_premise"], item[f"{lang}_answer"])])[0]
                        probabilities = [scores.entailment, scores.neutral, scores.contradiction]
                        record.update(predicted=LABELS[max(range(3), key=probabilities.__getitem__)], scores=probabilities)
                    else:
                        result = guard.apply_guard(item[f"{lang}_answer"], [item["en_premise"]], "", lang)
                        removal_mask(item[f"{lang}_answer"], result)
                        record.update(predicted=whole_verdict(result["claims"]), result=result, changed=result["changed"])
                    record["predicted_error"] = record["predicted"] in ERRORS
                else:
                    result = guard.apply_guard(item["answer"], item["context"], item["instructions"], "en")
                    mask = removal_mask(item["answer"], result)
                    record.update(result=result, changed=result["changed"], gold_error=bool(item["gold_spans"]),
                                  predicted_error=any(c["verdict"] in ERRORS for c in result["claims"]),
                                  spans=score_spans(item["answer"], item["gold_spans"], mask),
                                  task=item["task"], quality=item["quality"], model=item["model"],
                                  gold_spans=item["gold_spans"], annotations=item["annotations"])
                    # Declared adaptive evaluation sensitivities; never alter inference.
                    for name, excluded_flag in (("excluding_implicit_true", "implicit_true"), ("excluding_due_to_null", "due_to_null")):
                        spans = [[a["start"], a["end"]] for a in item["annotations"] if not a.get(excluded_flag)]
                        record[name] = dict(gold_error=bool(spans), spans=score_spans(item["answer"], spans, mask))
            except Exception:
                record["error"] = traceback.format_exc()
                print(record["error"], flush=True)
            consecutive_errors = consecutive_errors + 1 if "error" in record else 0
            record.update(elapsed_seconds=time.perf_counter() - case_started, truncation=dict(counters))
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            output.flush()
            previous.append(record)
            if consecutive_errors >= 3:
                raise RuntimeError("Stopped after three consecutive inference failures; preserve evidence and investigate")
            if index % 25 == 0 or index == len(work) or args.limit:
                print(f"{key}: {index}/{len(work)} elapsed={time.perf_counter() - started:.1f}s last={record['elapsed_seconds']:.3f}s", flush=True)
    save(run / "completion.json", dict(expected=len(work), rows=len(previous), failures=sum("error" in r for r in previous),
                                       current_session_seconds=time.perf_counter() - started, completed=True,
                                       peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated() if args.device == "cuda" else None))
    report(args.run_name, output=candidate_output if args.action_candidate else OUTPUT)
    return int(any("error" in r for r in previous))


def report(run_name: str, *, output: Path = OUTPUT) -> dict:
    run = output / run_name
    rows = [json.loads(line) for line in (run / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
    groups = {}
    for key in sorted({f"{r['dataset']}/{r['lang']}/{r['condition']}" for r in rows}):
        selected = [r for r in rows if f"{r['dataset']}/{r['lang']}/{r['condition']}" == key]
        groups[key] = summarize_group(selected)
        groups[key]["detection_ci95"] = cluster_intervals(selected)
    rag = [r for r in rows if r["dataset"] == "ragtruth"]
    for field in ("task", "quality", "model"):
        for value in sorted({r.get(field, "unknown") for r in rag}):
            groups[f"ragtruth/{field}/{value}"] = summarize_group([r for r in rag if r.get(field, "unknown") == value])
    for name in ("excluding_implicit_true", "excluding_due_to_null"):
        selected = [{**r, **r[name]} for r in rag if "error" not in r]
        if selected:
            groups[f"ragtruth/{name}"] = summarize_group(selected)
    gaps = {}
    for condition in ("raw", "guard"):
        en, ml = groups.get(f"nli/en/{condition}"), groups.get(f"nli/ml/{condition}")
        if en and ml:
            gaps[condition] = language_gaps(
                [r for r in rows if r["dataset"] == "nli" and r["lang"] == "en" and r["condition"] == condition],
                [r for r in rows if r["dataset"] == "nli" and r["lang"] == "ml" and r["condition"] == condition])
    result = dict(groups=groups, en_minus_ml=gaps, rows=len(rows), failures=sum("error" in r for r in rows))
    save(run / "metrics.json", result)
    print(json.dumps({"run": run_name, "rows": len(rows), "failures": result["failures"],
                      "groups": {k: {"selected": g["selected"], "detection": g["detection"],
                                     "false_alteration_rate": g["false_alteration_rate"], "latency": g["latency"]}
                                 for k, g in groups.items() if k.count("/") == 2 and k.split("/")[1] in {"en", "ml"}}}, indent=2), flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--download", action="store_true")
    mode.add_argument("--validate", action="store_true")
    mode.add_argument("--evaluate", action="store_true")
    mode.add_argument("--report", action="store_true")
    parser.add_argument("--benchmark", choices=("all", "nli", "ragtruth"), default="all")
    parser.add_argument("--conditions", choices=("raw", "guard", "raw,guard"), default="raw,guard")
    parser.add_argument("--languages", choices=("en", "ml", "en,ml"), default="en,ml")
    parser.add_argument("--action-candidate", action="store_true", help="Run passed English action candidate in versioned output")
    parser.add_argument("--run-name", default="full")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--limit", type=int, default=0, help="Fixed first N per dataset for preflight only; 0 evaluates all")
    args = parser.parse_args()
    if args.limit < 0 or not args.run_name or Path(args.run_name).name != args.run_name or args.run_name in {".", "..", "data"}:
        parser.error("Invalid limit or run-name")
    if args.action_candidate and (args.languages != "en" or args.conditions != "guard" or args.benchmark not in {"nli", "ragtruth", "all"}):
        parser.error("Action candidate requires --languages en --conditions guard")
    if args.download:
        download()
    elif args.validate:
        validate()
    elif args.report:
        report(args.run_name, output=ROOT / "results/guard-action-policy-2026-10-27" if args.action_candidate else OUTPUT)
    else:
        return evaluate(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
