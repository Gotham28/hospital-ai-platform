"""Train-only, source-grouped English guard action calibration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import time
from types import SimpleNamespace

from backend.research.guard.action_policy import ActionPolicy, should_alter
from backend.research.guard.claims import split_claims
from backend.research.guard.eval_external import adapt_ragtruth, removal_mask, score_spans
from backend.research.run_guard_external import OUTPUT as PUBLIC_OUTPUT, sha

ROOT = Path(__file__).resolve().parent
LEGACY_OUT = ROOT / "results/guard-action-policy-2026-10-27"
V5_OUT = ROOT / "results/guard-parser-v5-2026-10-28"
MANIFEST_PATH = LEGACY_OUT / "development-manifest.json"
OUT = LEGACY_OUT
TRACE_VERSION = "v4"
OUTPUT_VERSION = "v4"


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_inputs() -> tuple[dict, dict[str, dict]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    data = PUBLIC_OUTPUT / "data"
    if sha(data / "rag-source.jsonl") != manifest["source_sha256"] or sha(data / "rag-response.jsonl") != manifest["responses_sha256"]:
        raise ValueError("Pinned RAGTruth data drift")
    sources = {str(row["source_id"]): row for row in (json.loads(line) for line in (data / "rag-source.jsonl").read_text(encoding="utf-8").splitlines())}
    responses = {}
    for line in (data / "rag-response.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["split"] == "train":
            item = adapt_ragtruth(row, sources[str(row["source_id"])], required_split="train")
            responses[item["id"]] = item
    return manifest, responses


def selected_items(manifest: dict, responses: dict[str, dict], split: str) -> list[dict]:
    groups = set(manifest["split_groups"][split])
    items = [item for item in responses.values() if item["group"] in groups]
    if len(items) != manifest["counts"][split]["responses"] or {item["group"] for item in items} != groups:
        raise ValueError("Frozen source-group split drift")
    return sorted(items, key=lambda item: item["id"])


def trace_paths(split: str) -> tuple[Path, Path]:
    if split not in {"development", "validation"}:
        raise ValueError("Unknown calibration split")
    return OUT / f"{split}-{TRACE_VERSION}-identity.json", OUT / f"{split}-{TRACE_VERSION}-traces.jsonl"


def expected_trace_identity(split: str, device: str, items: list[dict] | None = None) -> dict:
    from backend.research.run_guard_performance import _verify_cache
    import torch
    import transformers
    sources = (Path(__file__), ROOT / "guard/action_policy.py", ROOT / "guard/guard.py",
               ROOT / "guard/conflict.py", ROOT / "guard/eval_external.py", ROOT / "guard/nli.py",
               ROOT / "guard/claims.py", ROOT / "guard/thresholds.json",
               ROOT / "run_guard_external.py", ROOT / "run_guard_performance.py")
    identity = dict(trace_version=TRACE_VERSION, split=split, device=device, dtype="float32", tf32=False,
                manifest_sha256=sha(MANIFEST_PATH),
                producer_sha256={path.relative_to(ROOT.parents[1]).as_posix(): sha(path) for path in sources},
                model_revisions=_verify_cache(), torch_version=torch.__version__,
                transformers_version=transformers.__version__, tokenizer_max_length=512)
    if OUTPUT_VERSION == "v5":
        if items is None:
            raise ValueError("V5 identity requires the selected item set")
        ids = [item["id"] for item in items]
        identity.update(output_version="v5", selected_count=len(ids),
                        selected_ids_sha256=sha_bytes("\n".join(ids).encode("utf-8")))
    return identity


def validate_trace_identity(split: str, *, device: str | None = None) -> dict:
    identity_path, trace_path = trace_paths(split)
    if not identity_path.is_file():
        raise ValueError(f"Missing {split} trace identity")
    saved = json.loads(identity_path.read_text(encoding="utf-8"))
    if not isinstance(saved, dict) or saved.get("device") not in {"cpu", "cuda"}:
        raise ValueError(f"{split} trace identity drift")
    items = None
    if OUTPUT_VERSION == "v5":
        manifest, responses = load_inputs()
        items = selected_items(manifest, responses, split)
        if TRACE_VERSION == "v5-preflight":
            items = items[:8]
    if saved != expected_trace_identity(split, device or saved["device"], items):
        raise ValueError(f"{split} trace identity drift")
    if not trace_path.is_file():
        raise ValueError(f"Missing {split} trace rows")
    return saved


def trace(split: str, device: str) -> None:
    from backend.research.run_guard_performance import _deny_network, _offline, _verify_cache
    _offline()
    _verify_cache()
    socket.socket.connect = _deny_network
    socket.socket.connect_ex = _deny_network
    socket.create_connection = _deny_network
    manifest, responses = load_inputs()
    items = selected_items(manifest, responses, split)
    if OUTPUT_VERSION == "v5" and TRACE_VERSION == "v5-preflight":
        items = items[:8]
    identity = expected_trace_identity(split, device, items if OUTPUT_VERSION == "v5" else None)
    identity_path, trace_path = trace_paths(split)
    OUT.mkdir(parents=True, exist_ok=True)
    if identity_path.exists():
        if not trace_path.exists():
            raise ValueError("Trace identity exists without trace rows")
        validate_trace_identity(split, device=device)
    elif trace_path.exists():
        raise ValueError("Trace exists without identity")
    previous = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()] if trace_path.exists() else []
    if len({row["id"] for row in previous}) != len(previous) or {row["id"] for row in previous} - {item["id"] for item in items}:
        raise ValueError("Trace resume contains duplicate or unexpected IDs")
    import torch
    from backend.research.guard import guard
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    torch.set_float32_matmul_precision("highest")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    scorer = guard._scorer()
    if device == "cuda":
        scorer.device = torch.device("cuda")
        scorer._model.to(device=scorer.device, dtype=torch.float32)
        if next(scorer._model.parameters()).device.type != "cuda":
            raise RuntimeError("CUDA requested but model did not load on CUDA")
        torch.cuda.reset_peak_memory_stats()
    _, thresholds = guard._thresholds("en")
    if not identity_path.exists():
        save(identity_path, identity)
    done = {row["id"] for row in previous}
    print(f"{split}: {len(done)}/{len(items)} completed; {device}; float32; offline", flush=True)
    with trace_path.open("a", encoding="utf-8") as output:
        for index, item in enumerate(items, 1):
            if item["id"] in done:
                continue
            started = time.perf_counter()
            claims = []
            for claim in split_claims(item["answer"], "en"):
                assessment = scorer.assess(claim, item["context"], entailment_threshold=thresholds.entailment,
                                           contradiction_threshold=thresholds.contradiction)
                claims.append(dict(text=claim, verdict=assessment.verdict, exact_verdict=assessment.exact_verdict,
                                   scores=vars(assessment.scores)))
            row = dict(id=item["id"], group=item["group"], task=item["task"], quality=item["quality"],
                       gold_spans=item["gold_spans"], claims=claims, inference_seconds=time.perf_counter()-started)
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
            output.flush()
            if index % 25 == 0 or index == len(items):
                print(f"{split}: {index}/{len(items)} last={row['inference_seconds']:.3f}s", flush=True)
    completion = dict(split=split, selected=len(items), completed=len(items), failures=0, device=device,
                      dtype="float32", tf32=False,
                      peak_gpu_memory_bytes=torch.cuda.max_memory_allocated() if device == "cuda" else None,
                      trace_version=TRACE_VERSION)
    if OUTPUT_VERSION == "v5":
        save(OUT / "run-metadata.json", completion)
    print(json.dumps(completion, sort_keys=True), flush=True)


def score_policy(item: dict, trace_row: dict, policy: ActionPolicy) -> dict:
    answer = item["answer"]
    final = answer
    claims = []
    for claim in trace_row["claims"]:
        altered = should_alter(claim["verdict"], SimpleNamespace(**claim["scores"]), claim["exact_verdict"], policy)
        claims.append(dict(text=claim["text"], verdict=claim["verdict"], altered=altered))
        if altered:
            final = final.replace(claim["text"], "[FLAG_TEXT]")
    result = dict(final_answer=final, claims=claims)
    mask = removal_mask(answer, result)
    spans = score_spans(answer, item["gold_spans"], mask)
    return dict(id=item["id"], group=item["group"], task=item["task"], quality=item["quality"],
                gold_error=bool(item["gold_spans"]), predicted_error=any(c["verdict"] in {"unsupported", "contradicted"} for c in claims),
                changed=bool(mask), spans=spans, inference_seconds=trace_row["inference_seconds"])


def metrics(rows: list[dict], *, include_subgroups: bool = True) -> dict:
    import numpy as np
    clean = [r for r in rows if not r["gold_error"]]
    erroneous = [r for r in rows if r["gold_error"]]
    intercepted = sum(bool(r["spans"]["fully_intercepted"]) for r in erroneous)
    by_group = {}
    for row in rows:
        by_group.setdefault(row["group"], []).append(row)
    vectors = np.asarray([[sum(not r["gold_error"] for r in group),
                           sum(not r["gold_error"] and r["changed"] for r in group),
                           sum(r["gold_error"] for r in group),
                           sum(r["gold_error"] and bool(r["spans"]["fully_intercepted"]) for r in group)]
                          for group in by_group.values()], dtype=float)
    rng = np.random.default_rng(20261027)
    samples = vectors[rng.integers(len(vectors), size=(2000, len(vectors)))].sum(axis=1)
    def interval(numer, denom):
        values = np.divide(numer, denom, out=np.full_like(numer, np.nan), where=denom != 0)
        return [float(x) for x in np.nanpercentile(values, [2.5, 97.5])] if np.isfinite(values).any() else None
    tp_chars = sum(r["spans"]["tp_chars"] for r in rows)
    fp_chars = sum(r["spans"]["fp_chars"] for r in rows)
    fn_chars = sum(r["spans"]["fn_chars"] for r in rows)
    elapsed = [r["inference_seconds"] for r in rows]
    result = dict(n=len(rows), clean=len(clean), erroneous=len(erroneous), false_alterations=sum(r["changed"] for r in clean),
                false_alteration_rate=sum(r["changed"] for r in clean)/len(clean) if clean else None,
                fully_intercepted=intercepted, fully_intercepted_rate=intercepted/len(erroneous) if erroneous else None,
                missed_error_answers=len(erroneous)-intercepted, residual_error_answers=len(erroneous)-intercepted,
                detection_tp=sum(r["gold_error"] and r["predicted_error"] for r in rows),
                detection_fp=sum(not r["gold_error"] and r["predicted_error"] for r in rows),
                changed_answers=sum(r["changed"] for r in rows), changed_answer_rate=sum(r["changed"] for r in rows)/len(rows),
                tp_chars=tp_chars, fp_chars=fp_chars, fn_chars=fn_chars,
                character_precision=tp_chars/(tp_chars+fp_chars) if tp_chars+fp_chars else None,
                character_recall=tp_chars/(tp_chars+fn_chars) if tp_chars+fn_chars else None,
                latency_seconds=dict(n=len(elapsed), mean=float(np.mean(elapsed)), p50=float(np.percentile(elapsed, 50)),
                                     p95=float(np.percentile(elapsed, 95))),
                ci95=dict(method="source-cluster percentile bootstrap", groups=len(vectors), samples=2000,
                          false_alteration_rate=interval(samples[:, 1], samples[:, 0]),
                          fully_intercepted_rate=interval(samples[:, 3], samples[:, 2])))
    if include_subgroups:
        for field, output_key in (("task", "task_subgroups"), ("quality", "quality_subgroups")):
            buckets = {}
            for row in rows:
                buckets.setdefault(str(row[field]), []).append(row)
            result[output_key] = {name: metrics(group, include_subgroups=False) for name, group in sorted(buckets.items())}
    return result


def analyze(split: str) -> None:
    validate_trace_identity(split)
    manifest, responses = load_inputs()
    items = selected_items(manifest, responses, split)
    _, trace_path = trace_paths(split)
    traces = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    indexed = {row["id"]: row for row in traces}
    if len(traces) != len(items) or len(indexed) != len(items) or set(indexed) != {item["id"] for item in items}:
        raise ValueError("Incomplete or duplicate traces")
    policies = [ActionPolicy(**value) for value in manifest["candidate_policies"]]
    if split == "validation":
        chosen = json.loads((OUT / "development-selection.json").read_text(encoding="utf-8"))["selected"]
        policies = [p for p in policies if p.name in {"baseline", chosen}]
    results = {}
    for policy in policies:
        rows = [score_policy(item, indexed[item["id"]], policy) for item in items]
        results[policy.name] = metrics(rows)
    output = dict(split=split, manifest_sha256=sha(MANIFEST_PATH), results=results)
    save(OUT / f"{split}-metrics.json", output)
    if split == "development":
        baseline = results["baseline"]
        eligible = [(name, result) for name, result in results.items() if name != "baseline"
                    and result["fully_intercepted_rate"] >= .5 * baseline["fully_intercepted_rate"]
                    and baseline["false_alteration_rate"] - result["false_alteration_rate"] >= .2]
        chosen = min(eligible, key=lambda x: (x[1]["false_alteration_rate"], -x[1]["fully_intercepted_rate"], x[0]))[0] if eligible else "baseline"
        save(OUT / "development-selection.json", dict(selected=chosen, rule=manifest["selection_rule"], eligible=[name for name, _ in eligible],
                                                       development_metrics_sha256=sha(OUT / "development-metrics.json")))
        print(f"development selected={chosen}; eligible={len(eligible)}", flush=True)
    else:
        chosen = json.loads((OUT / "development-selection.json").read_text(encoding="utf-8"))["selected"]
        base, candidate = results["baseline"], results[chosen]
        passed = (chosen != "baseline" and candidate["fully_intercepted_rate"] >= .5*base["fully_intercepted_rate"]
                  and base["false_alteration_rate"]-candidate["false_alteration_rate"] >= .2)
        save(OUT / "validation-decision.json", dict(selected=chosen, passed=passed,
                                                       false_alteration_reduction=base["false_alteration_rate"]-candidate["false_alteration_rate"],
                                                       interception_retention=candidate["fully_intercepted_rate"]/base["fully_intercepted_rate"] if base["fully_intercepted_rate"] else None,
                                                       validation_metrics_sha256=sha(OUT / "validation-metrics.json")))
        print(f"validation selected={chosen}; passed={passed}", flush=True)
    print(json.dumps(results, indent=2), flush=True)


def sha_bytes(value: bytes) -> str:
    import hashlib
    return hashlib.sha256(value).hexdigest()


def configure_output(version: str, *, preflight: bool = False) -> None:
    """Route new parser evidence away from the immutable v4 result directory."""
    global OUT, TRACE_VERSION, OUTPUT_VERSION
    if version == "v4":
        if preflight:
            raise ValueError("A bounded preflight is only supported for v5 output")
        OUT, TRACE_VERSION, OUTPUT_VERSION = LEGACY_OUT, "v4", "v4"
        return
    if version != "v5":
        raise ValueError(f"Unknown output version: {version}")
    OUTPUT_VERSION = "v5"
    if preflight:
        OUT, TRACE_VERSION = V5_OUT / "preflight-8", "v5-preflight"
    else:
        OUT, TRACE_VERSION = V5_OUT, "v5"


def verify_v5() -> None:
    """Verify the complete v5 development run and its immutable v4 inputs."""
    import math
    manifest, responses = load_inputs()
    items = selected_items(manifest, responses, "development")
    identity = validate_trace_identity("development", device="cuda")
    _, trace_path = trace_paths("development")
    traces = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    ids = [row["id"] for row in traces]
    if len(ids) != len(set(ids)) or set(ids) != {item["id"] for item in items}:
        raise ValueError("Missing, duplicate, or unexpected v5 development trace IDs")
    score_count = 0
    for row in traces:
        for claim in row["claims"]:
            values = claim["scores"]
            if not all(math.isfinite(value) and 0 <= value <= 1 for value in values.values()) or abs(sum(values.values()) - 1) > 1e-4:
                raise ValueError("Invalid cached v5 probability vector")
            score_count += 1
    protected_path = V5_OUT / "v4-protected-hashes.json"
    protected = json.loads(protected_path.read_text(encoding="utf-8"))
    actual = {name: sha(ROOT.parents[1] / name) for name in protected}
    if actual != protected:
        raise ValueError("Protected v4 artifacts changed during v5 evaluation")
    report = dict(output_version="v5", split="development", device=identity["device"], dtype=identity["dtype"],
                  tf32=identity["tf32"], selected=len(items), completed=len(traces), unique_ids=len(set(ids)),
                  claim_scores=score_count, manifest_sha256=identity["manifest_sha256"],
                  producer_sha256=identity["producer_sha256"], model_revisions=identity["model_revisions"],
                  torch_version=identity["torch_version"], transformers_version=identity["transformers_version"],
                  v4_artifacts_checked=len(protected), v4_artifacts_match=True)
    save(V5_OUT / "verification-v5.json", report)
    print(json.dumps(report, indent=2), flush=True)


def audit_tokens(split: str) -> None:
    from backend.research.run_guard_performance import _offline
    from backend.research.guard.nli import MODEL_CACHE, MODEL_ID
    from transformers import AutoTokenizer
    _offline()
    validate_trace_identity(split)
    manifest, responses = load_inputs()
    items = selected_items(manifest, responses, split)
    _, trace_path = trace_paths(split)
    indexed = {row["id"]: row for row in (json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines())}
    if set(indexed) != {item["id"] for item in items}:
        raise ValueError("Incomplete traces for token audit")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, cache_dir=MODEL_CACHE, local_files_only=True)
    counts = []
    for item in items:
        for claim in indexed[item["id"]]["claims"]:
            for passage in item["context"]:
                counts.append(len(tokenizer(passage, claim["text"], truncation=False, verbose=False)["input_ids"]))
    save(OUT / f"{split}-token-audit.json", dict(pairs=len(counts), truncated_pairs=sum(n > 512 for n in counts),
                                                  max_untruncated_tokens=max(counts, default=0), tokenizer=MODEL_ID,
                                                  split=split, manifest_sha256=sha(MANIFEST_PATH)))
    print(f"{split}: pairs={len(counts)} truncated={sum(n > 512 for n in counts)}", flush=True)


def verify_artifacts() -> None:
    import math
    from backend.research.guard.action_policy import ACTIVE_ENGLISH, BASELINE
    manifest, responses = load_inputs()
    selected = {split: selected_items(manifest, responses, split) for split in ("development", "validation")}
    groups = {split: {item["group"] for item in items} for split, items in selected.items()}
    if groups["development"] & groups["validation"]:
        raise ValueError("Development/validation source overlap")
    trace_counts = {}
    legacy_action_checks = 0
    for split, items in selected.items():
        validate_trace_identity(split)
        _, trace_path = trace_paths(split)
        traces = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
        ids = [row["id"] for row in traces]
        if len(ids) != len(set(ids)) or set(ids) != {item["id"] for item in items}:
            raise ValueError(f"Missing or duplicate {split} traces")
        for row in traces:
            for claim in row["claims"]:
                scores = claim["scores"]
                if not all(math.isfinite(value) and 0 <= value <= 1 for value in scores.values()) or abs(sum(scores.values()) - 1) > 1e-4:
                    raise ValueError("Invalid cached probability vector")
                if should_alter(claim["verdict"], SimpleNamespace(**scores), claim["exact_verdict"], ACTIVE_ENGLISH) != (claim["verdict"] in {"unsupported", "contradicted"}):
                    raise ValueError("Active English action differs from legacy verdict-based redaction")
                legacy_action_checks += 1
        trace_counts[split] = len(traces)
    baseline = json.loads((OUT / "baseline.json").read_text(encoding="utf-8"))
    protected = {name: value for name, value in baseline["hashes"].items() if name in {
        "backend/research/guard/nli.py", "backend/research/guard/claims.py", "backend/research/guard/conflict.py",
        "backend/research/guard/factlock.py", "backend/research/guard/thresholds.json",
        "backend/research/results/guard-external-2026-10-26/full-cuda/metrics.json",
        "backend/research/results/guard-external-2026-10-26/full-cuda/completion.json"}}
    for name, checksum in protected.items():
        if sha(ROOT.parents[1] / name) != checksum:
            raise ValueError(f"Protected baseline drift: {name}")
    if ACTIVE_ENGLISH != BASELINE:
        raise ValueError("No candidate qualified, but baseline is not active")
    decision = json.loads((OUT / "validation-decision.json").read_text(encoding="utf-8"))
    if decision["passed"] or decision["selected"] != "baseline":
        raise ValueError("Validation decision contradicts frozen selection")
    changed_sources = ["backend/research/guard/guard.py", "backend/research/guard/action_policy.py",
                       "backend/research/guard/eval_external.py", "backend/research/run_guard_calibration.py",
                       "backend/research/run_guard_external.py"]
    summary = dict(manifest_sha256=sha(MANIFEST_PATH), train_only=True,
                   group_overlap=0, selected_responses={split: len(items) for split, items in selected.items()},
                   trace_counts=trace_counts, protected_hashes_match=len(protected), active_policy=ACTIVE_ENGLISH.name,
                   candidate_promoted=False, legacy_action_checks=legacy_action_checks,
                   current_source_sha256={name: sha(ROOT.parents[1] / name) for name in changed_sources})
    save(OUT / "verification.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


def smoke_baseline() -> None:
    """Compare the first published EN/ML pair with the frozen full-run output."""
    from backend.research.run_guard_performance import _deny_network, _offline, _verify_cache
    from backend.research.run_guard_external import load_items
    _offline()
    _verify_cache()
    socket.socket.connect = _deny_network
    socket.socket.connect_ex = _deny_network
    socket.create_connection = _deny_network
    import torch
    from backend.research.guard import guard
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable for pinned benchmark smoke")
    torch.set_float32_matmul_precision("highest")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    scorer = guard._scorer()
    scorer.device = torch.device("cuda")
    scorer._model.to(device=scorer.device, dtype=torch.float32)
    translator = guard._translator()
    translator.device = torch.device("cuda")
    translator.model.to(device=translator.device, dtype=torch.float32)
    first = load_items()[0][0]
    keys = {f"nli/{lang}/guard/{first['id']}" for lang in ("en", "ml")}
    frozen = {}
    for line in (PUBLIC_OUTPUT / "full-cuda/cases.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["key"] in keys:
            frozen[row["key"]] = row["result"]
    if set(frozen) != keys:
        raise ValueError("First paired full-run outputs absent")
    matches = {}
    for lang in ("en", "ml"):
        key = f"nli/{lang}/guard/{first['id']}"
        result = guard.apply_guard(first[f"{lang}_answer"], [first["en_premise"]], "", lang)
        normalized = {**result, "claims": [{k: v for k, v in claim.items() if k != "altered"} for claim in result["claims"]]}
        matches[lang] = normalized == frozen[key]
        if not matches[lang]:
            raise ValueError(f"{lang} assembled guard differs from frozen baseline case")
    print(json.dumps(dict(first_pair_id=first["id"], exact_result_match=matches, device="cuda", precision="float32"), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("development", "validation"))
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--analyze-only", action="store_true")
    parser.add_argument("--audit-tokens", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--smoke-baseline", action="store_true")
    parser.add_argument("--output-version", choices=("v4", "v5"), default="v4")
    parser.add_argument("--preflight", action="store_true", help="Run the fixed 8-answer v5 CUDA preflight only")
    args = parser.parse_args()
    configure_output(args.output_version, preflight=args.preflight)
    if args.smoke_baseline:
        smoke_baseline()
        return
    if args.preflight and (args.verify or args.smoke_baseline):
        parser.error("--preflight cannot be combined with verification or smoke mode")
    if args.verify:
        verify_v5() if OUTPUT_VERSION == "v5" else verify_artifacts()
        return
    if args.split is None:
        parser.error("--split is required unless --verify is used")
    if args.split == "validation" and not (OUT / "development-selection.json").exists():
        parser.error("Select on development before validation")
    if args.preflight and (OUTPUT_VERSION != "v5" or args.split != "development" or args.device != "cuda" or args.analyze_only or args.audit_tokens):
        parser.error("--preflight requires --output-version v5 --split development --device cuda and inference mode")
    if OUTPUT_VERSION == "v5" and args.split != "development":
        parser.error("V5 output is development-only")
    if args.analyze_only and args.audit_tokens:
        parser.error("Choose one postprocessing mode")
    if args.audit_tokens:
        audit_tokens(args.split)
        return
    if not args.analyze_only:
        trace(args.split, args.device)
    if args.preflight:
        return
    analyze(args.split)


if __name__ == "__main__":
    main()
