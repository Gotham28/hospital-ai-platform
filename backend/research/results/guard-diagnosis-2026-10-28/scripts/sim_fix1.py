import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from backend.research.guard.nli import NLIScores, ClaimAssessment, _decompose_passages, _select_candidate_passages, _typed_values
from backend.research.guard.action_policy import BASELINE, should_alter
from backend.research.guard.eval_external import removal_mask
from backend.research.guard import guard
from backend.research.replay.cache import NLICache, make_key
from backend.research.run_guard_calibration import load_inputs, selected_items, score_policy, metrics

cache_path = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl"
cache = NLICache(cache_path)
manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}

traces_path = repo_root / "backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl"
stored_traces = [json.loads(line) for line in traces_path.read_text(encoding="utf-8").splitlines()]
stored_by_id = {str(t["id"]): t for t in stored_traces}

rag_response_path = repo_root / "backend/research/results/guard-external-2026-10-26/data/rag-response.jsonl"
rag_labels_by_id = {}
with open(rag_response_path, "r", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("labels"):
            rag_labels_by_id[str(r["id"])] = r["labels"]

_, thresholds = guard._thresholds("en")
ethresh = thresholds.entailment
cthresh = thresholds.contradiction

STOPS = {"a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or", "is", "was", "are", "were", "it", "this", "that"}

def assess_variant(variant: str, claim: str, context: list[str]) -> ClaimAssessment:
    active_passages = _select_candidate_passages(claim, _decompose_passages(context), max_candidates=4)
    claim_values = _typed_values(claim)
    context_values = [_typed_values(passage) for passage in active_passages]
    exact_verdict = None
    exact_evidence = None
    for kind, values in claim_values.items():
        if not values:
            continue
        for passage, passage_values in zip(active_passages, context_values):
            expected = passage_values[kind]
            if expected and values.isdisjoint(expected):
                exact_verdict, exact_evidence = "contradicted", passage
                break
        if exact_verdict:
            break
    if any(claim_values.values()) and not any(
        values for passage_values in context_values for values in passage_values.values()
    ):
        exact_verdict = "unsupported"

    scores = [cache.get(make_key(passage, claim)) for passage in active_passages]
    assert all(s is not None for s in scores)

    if variant == "baseline":
        best_index = max(
            range(len(scores)),
            key=lambda index: max(scores[index].entailment, scores[index].contradiction)
        )
        best = scores[best_index]
        if best.contradiction >= cthresh and best.contradiction > best.entailment:
            verdict = "contradicted"
        elif best.entailment >= ethresh:
            verdict = "supported"
        else:
            verdict = "unsupported"
            
    elif variant == "A":
        # (A) best-entailment passage first; if it clears the entailment threshold -> supported; else existing contradiction logic.
        best_e_idx = max(range(len(scores)), key=lambda i: scores[i].entailment)
        if scores[best_e_idx].entailment >= ethresh:
            best_index = best_e_idx
            best = scores[best_index]
            verdict = "supported"
        else:
            # existing contradiction logic
            best_c_idx = max(range(len(scores)), key=lambda i: scores[i].contradiction)
            best_c = scores[best_c_idx]
            if best_c.contradiction >= cthresh and best_c.contradiction > best_c.entailment:
                best_index = best_c_idx
                best = best_c
                verdict = "contradicted"
            else:
                best_index = best_e_idx
                best = scores[best_e_idx]
                verdict = "unsupported"

    elif variant == "B":
        # (B) as A, but contradiction only counts if the contradicting passage shares a content word or entity with the claim.
        best_e_idx = max(range(len(scores)), key=lambda i: scores[i].entailment)
        if scores[best_e_idx].entailment >= ethresh:
            best_index = best_e_idx
            best = scores[best_index]
            verdict = "supported"
        else:
            # check content word sharing for contradiction candidates
            claim_tokens = set(re.findall(r"\w+", claim.casefold()))
            claim_terms = claim_tokens - STOPS or claim_tokens
            
            c_cands = []
            for i, p in enumerate(active_passages):
                p_tokens = set(re.findall(r"\w+", p.casefold()))
                if claim_terms & p_tokens:
                    c_cands.append(i)
            
            if c_cands:
                best_c_idx = max(c_cands, key=lambda i: scores[i].contradiction)
                best_c = scores[best_c_idx]
                if best_c.contradiction >= cthresh and best_c.contradiction > best_c.entailment:
                    best_index = best_c_idx
                    best = best_c
                    verdict = "contradicted"
                else:
                    best_index = best_e_idx
                    best = scores[best_e_idx]
                    verdict = "unsupported"
            else:
                best_index = best_e_idx
                best = scores[best_e_idx]
                verdict = "unsupported"

    if exact_verdict is not None:
        verdict = exact_verdict
    evidence = exact_evidence or active_passages[best_index]
    return ClaimAssessment(verdict, best, evidence, exact_verdict)


def evaluate(variant_name: str):
    replayed_traces = []
    for tid, item in dev_items.items():
        stored = stored_by_id[tid]
        re_claims = []
        for c_idx, stored_c in enumerate(stored["claims"]):
            claim_text = stored_c["text"]
            assessment = assess_variant(variant_name, claim_text, item["context"])
            re_claims.append({
                "text": claim_text,
                "verdict": assessment.verdict,
                "exact_verdict": assessment.exact_verdict,
                "scores": vars(assessment.scores),
            })
        replayed_traces.append({
            "id": tid,
            "group": stored["group"],
            "task": stored["task"],
            "quality": stored["quality"],
            "gold_spans": stored["gold_spans"],
            "claims": re_claims,
            "answer": item["answer"],
            "inference_seconds": 0.0,
        })

    replayed_by_id = {str(t["id"]): t for t in replayed_traces}
    eval_rows = [score_policy(item, replayed_by_id[item["id"]], BASELINE) for item in dev_items.values()]
    base_metrics = metrics(eval_rows, include_subgroups=False)

    clean_altered = base_metrics["false_alterations"]
    clean_total = base_metrics["clean"]
    err_intercepted = base_metrics["fully_intercepted"]
    err_total = base_metrics["erroneous"]
    char_prec = base_metrics["character_precision"]

    # Label-type interception
    label_totals = defaultdict(int)
    label_intercepted = defaultdict(int)
    for item in dev_items.values():
        tid = str(item["id"])
        labels = rag_labels_by_id.get(tid, [])
        if not labels:
            continue
        trace_row = replayed_by_id[tid]
        answer = item["answer"]
        final = answer
        claims = []
        for claim in trace_row["claims"]:
            altered = should_alter(claim["verdict"], SimpleNamespace(**claim["scores"]), claim["exact_verdict"], BASELINE)
            claims.append(dict(text=claim["text"], verdict=claim["verdict"], altered=altered))
            if altered:
                final = final.replace(claim["text"], "[FLAG_TEXT]")
        result = dict(final_answer=final, claims=claims)
        mask = removal_mask(answer, result)

        for lbl in labels:
            l_type = lbl["label_type"]
            span_set = set(range(lbl["start"], lbl["end"]))
            label_totals[l_type] += 1
            if span_set <= mask:
                label_intercepted[l_type] += 1

    by_type = {}
    for l_type in sorted(label_totals.keys()):
        tot = label_totals[l_type]
        inc = label_intercepted[l_type]
        by_type[l_type] = f"{inc}/{tot} ({inc/tot*100:.1f}%)"

    return {
        "variant": variant_name,
        "clean_altered": f"{clean_altered}/{clean_total} ({base_metrics['false_alteration_rate']*100:.2f}%)",
        "clean_altered_num": clean_altered,
        "intercepted": f"{err_intercepted}/{err_total} ({base_metrics['fully_intercepted_rate']*100:.2f}%)",
        "intercepted_num": err_intercepted,
        "char_precision": f"{char_prec:.4f}",
        "char_precision_val": char_prec,
        "by_type": by_type,
        "eval_rows": eval_rows,
        "replayed_traces": replayed_traces,
    }

for v in ["baseline", "A", "B"]:
    res = evaluate(v)
    print(f"\nVariant {res['variant']}:")
    print(f"  Clean altered  : {res['clean_altered']}")
    print(f"  Intercepted    : {res['intercepted']}")
    print(f"  Char precision : {res['char_precision']}")
    print("  By label type:")
    for k, val in res["by_type"].items():
        print(f"    {k:24}: {val}")
