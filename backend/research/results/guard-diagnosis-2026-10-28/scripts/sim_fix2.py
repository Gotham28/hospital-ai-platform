import json
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

def assess_mode(claim: str, context: list[str], fix1: bool, fix2: bool) -> ClaimAssessment:
    active_passages = _select_candidate_passages(claim, _decompose_passages(context), max_candidates=4)
    claim_values = _typed_values(claim)
    context_values = [_typed_values(passage) for passage in active_passages]
    exact_verdict = None
    exact_evidence = None

    if fix2:
        # Fix 2: Contradicted only if NO candidate passage contains a matching value of that kind AND at least one contains a conflicting value.
        for kind, values in claim_values.items():
            if not values:
                continue
            has_matching = any(not values.isdisjoint(pv[kind]) for pv in context_values if pv[kind])
            conflicting = [p for p, pv in zip(active_passages, context_values) if pv[kind] and values.isdisjoint(pv[kind])]
            if conflicting and not has_matching:
                exact_verdict, exact_evidence = "contradicted", conflicting[0]
                break
    else:
        # Original exact-match loop
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

    if fix1:
        # Fix 1: best-entailment passage first
        best_e_index = max(range(len(scores)), key=lambda index: scores[index].entailment)
        if scores[best_e_index].entailment >= ethresh:
            verdict = "supported"
            best_index = best_e_index
            best = scores[best_index]
        else:
            best_index = max(range(len(scores)), key=lambda index: max(scores[index].entailment, scores[index].contradiction))
            best = scores[best_index]
            if best.contradiction >= cthresh and best.contradiction > best.entailment:
                verdict = "contradicted"
            elif best.entailment >= ethresh:
                verdict = "supported"
            else:
                verdict = "unsupported"
    else:
        # Baseline passage selection
        best_index = max(range(len(scores)), key=lambda index: max(scores[index].entailment, scores[index].contradiction))
        best = scores[best_index]
        if best.contradiction >= cthresh and best.contradiction > best.entailment:
            verdict = "contradicted"
        elif best.entailment >= ethresh:
            verdict = "supported"
        else:
            verdict = "unsupported"

    if exact_verdict is not None:
        verdict = exact_verdict
    evidence = exact_evidence or active_passages[best_index]
    return ClaimAssessment(verdict, best, evidence, exact_verdict)

def run_eval(fix1: bool, fix2: bool):
    traces = []
    for tid, item in dev_items.items():
        stored = stored_by_id[tid]
        re_claims = []
        for c_idx, stored_c in enumerate(stored["claims"]):
            claim_text = stored_c["text"]
            assessment = assess_mode(claim_text, item["context"], fix1, fix2)
            re_claims.append({
                "text": claim_text,
                "verdict": assessment.verdict,
                "exact_verdict": assessment.exact_verdict,
                "scores": vars(assessment.scores),
            })
        traces.append({
            "id": tid,
            "group": stored["group"],
            "task": stored["task"],
            "quality": stored["quality"],
            "gold_spans": stored["gold_spans"],
            "claims": re_claims,
            "answer": item["answer"],
            "inference_seconds": 0.0,
        })
    by_id = {str(t["id"]): t for t in traces}
    eval_rows = [score_policy(item, by_id[item["id"]], BASELINE) for item in dev_items.values()]
    m = metrics(eval_rows, include_subgroups=False)

    clean_altered = m["false_alterations"]
    clean_total = m["clean"]
    err_intercepted = m["fully_intercepted"]
    err_total = m["erroneous"]
    char_prec = m["character_precision"]

    # Label-type interception
    label_totals = defaultdict(int)
    label_intercepted = defaultdict(int)

    for item in dev_items.values():
        tid = str(item["id"])
        labels = rag_labels_by_id.get(tid, [])
        if not labels:
            continue
        trace_row = by_id[tid]
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

    by_type = {k: f"{label_intercepted[k]}/{label_totals[k]} ({label_intercepted[k]/label_totals[k]*100:.1f}%)" for k in sorted(label_totals.keys())}
    
    return {
        "clean_altered": f"{clean_altered}/{clean_total} ({m['false_alteration_rate']*100:.2f}%)",
        "clean_altered_num": clean_altered,
        "intercepted": f"{err_intercepted}/{err_total} ({m['fully_intercepted_rate']*100:.2f}%)",
        "intercepted_num": err_intercepted,
        "char_precision": f"{char_prec:.4f}",
        "by_type": by_type,
        "traces": traces,
        "eval_rows": eval_rows,
    }

print("Running baseline...")
base = run_eval(fix1=False, fix2=False)
print("Running Fix 2 ALONE...")
f2_alone = run_eval(fix1=False, fix2=True)
print("Running Fix 1 + Fix 2 CUMULATIVE...")
f1_f2 = run_eval(fix1=True, fix2=True)

print(f"\nBaseline:")
print(f"  Clean altered  : {base['clean_altered']}")
print(f"  Intercepted    : {base['intercepted']}")
print(f"  Char precision : {base['char_precision']}")

print(f"\nFix 2 ALONE vs baseline:")
print(f"  Clean altered  : {f2_alone['clean_altered']}")
print(f"  Intercepted    : {f2_alone['intercepted']}")
print(f"  Char precision : {f2_alone['char_precision']}")
print("  By label type:")
for k, v in f2_alone["by_type"].items():
    print(f"    {k:24}: {v}")

print(f"\nFix 1 + Fix 2 CUMULATIVE vs baseline:")
print(f"  Clean altered  : {f1_f2['clean_altered']}")
print(f"  Intercepted    : {f1_f2['intercepted']}")
print(f"  Char precision : {f1_f2['char_precision']}")
print("  By label type:")
for k, v in f1_f2["by_type"].items():
    print(f"    {k:24}: {v}")
