r"""
Diagnostic script for guard false-alteration causes.

Runs the BUNDLE v5 guard code on the guard_dev_set.json fixture
to measure, for 'supported' (clean) answers:
  - How many claims are produced per answer
  - For each flagged claim: cause (nli_only / exact_only / both)
  - Entailment score distribution for flagged claims
  - Specific examples

Reads bundle code via sys.path injection so we do NOT modify live files.
Uses backend/research/.venv/Scripts/python.exe

Usage (from repo root, PowerShell):
  backend\research\.venv\Scripts\python.exe -B `
    C:\Users\Sreehari\.gemini\antigravity-ide\brain\d3e4acec-ffb6-4824-b295-0bcf398df4e3\scratch\diagnose_guard.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

# --- path setup: add BUNDLE guard dir to path so we import v5 code --------
REPO = Path(__file__).resolve().parents[4]  # workspace root
BUNDLE_RESEARCH = REPO / "handoff/bundle/GUARD_AI_HANDOFF/backend/research"

# Add bundle to sys.path so `guard.*` resolves to bundle v5 code.
sys.path.insert(0, str(BUNDLE_RESEARCH))

# Also add repo root for any relative imports that may be needed.
sys.path.insert(0, str(REPO))

# Patch MODEL_CACHE to the live venv's cache (weights are there).
from guard import nli as nli_module
LIVE_VENV = REPO / "backend/venv/model_cache"
if LIVE_VENV.exists():
    nli_module.MODEL_CACHE = LIVE_VENV

from guard.nli import MultilingualNLIScorer, _typed_values, _decompose_passages, _select_candidate_passages
from guard.claims import split_claims

FIXTURE_PATH = REPO / "backend/research/fixtures/guard_dev_set.json"
THRESHOLDS = {"entailment": 0.9, "contradiction": 0.3}  # bundle v5 English direct

print("Loading fixture...", flush=True)
records = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
supported = [r for r in records if r["ground_truth"]["overall_verdict"] == "supported"]
print(f"Supported (clean-labeled) answers in fixture: {len(supported)}", flush=True)

print("Loading NLI model (bundle v5 code, live model cache)...", flush=True)
try:
    scorer = MultilingualNLIScorer(device="cuda")
    print("  -> CUDA loaded", flush=True)
except Exception as e:
    print(f"  -> CUDA failed ({e}), trying CPU...", flush=True)
    scorer = MultilingualNLIScorer(device="cpu")
    print("  -> CPU loaded", flush=True)

print("Running guard on clean answers...", flush=True)

results = []
for rec in supported:
    answer = rec["answer"]
    context = rec["context"]
    lang = rec.get("lang", "en")
    claims = split_claims(answer, lang)

    answer_flagged = False
    claim_details = []
    for claim in claims:
        # Typed-value exact check
        active = _select_candidate_passages(claim, _decompose_passages(context), max_candidates=4)
        claim_vals = _typed_values(claim)
        ctx_vals = [_typed_values(p) for p in active]
        exact_verdict = None
        for kind, vals in claim_vals.items():
            if not vals:
                continue
            for p, pv in zip(active, ctx_vals):
                if pv[kind] and vals.isdisjoint(pv[kind]):
                    exact_verdict = "contradicted"
                    break
            if exact_verdict:
                break
        if any(claim_vals.values()) and not any(
            v for pv in ctx_vals for v in pv.values()
        ):
            exact_verdict = "unsupported"

        # NLI score
        scores_list = scorer.score_pairs([(p, claim) for p in active])
        best = max(scores_list, key=lambda s: max(s.entailment, s.contradiction))
        best_idx = scores_list.index(best)

        if best.contradiction >= THRESHOLDS["contradiction"] and best.contradiction > best.entailment:
            nli_verdict = "contradicted"
        elif best.entailment >= THRESHOLDS["entailment"]:
            nli_verdict = "supported"
        else:
            nli_verdict = "unsupported"

        # Final verdict (exact overrides NLI if set)
        final_verdict = exact_verdict if exact_verdict is not None else nli_verdict

        flagged = final_verdict in {"unsupported", "contradicted"}
        if flagged:
            answer_flagged = True

        if exact_verdict is not None and nli_verdict in {"unsupported", "contradicted"}:
            cause = "both"
        elif exact_verdict is not None:
            cause = "exact_only"
        elif nli_verdict in {"unsupported", "contradicted"}:
            cause = "nli_only"
        else:
            cause = "none"

        claim_details.append({
            "claim": claim,
            "exact_verdict": exact_verdict,
            "nli_verdict": nli_verdict,
            "final_verdict": final_verdict,
            "entailment": best.entailment,
            "neutral": best.neutral,
            "contradiction": best.contradiction,
            "flagged": flagged,
            "cause": cause,
            "selected_passage": active[best_idx] if active else "",
            "n_active_passages": len(active),
            "claim_vals": {k: list(v) for k, v in claim_vals.items() if v},
        })

    results.append({
        "id": rec["id"],
        "answer": answer,
        "context": context,
        "phenomenon": rec.get("phenomenon", ""),
        "test_focus": rec.get("test_focus", ""),
        "n_claims": len(claims),
        "n_flagged": sum(1 for c in claim_details if c["flagged"]),
        "answer_altered": answer_flagged,
        "claims": claim_details,
    })

# ---- aggregate statistics ----
print("\n=== AGGREGATE RESULTS ===\n")

total = len(results)
altered = sum(1 for r in results if r["answer_altered"])
print(f"Clean answers: {total}")
print(f"Altered: {altered}/{total} = {altered/total:.1%}")
print()

# Cause breakdown across all flagged claims
cause_counts: dict[str, int] = {}
all_entailments_flagged = []
all_entailments_safe = []

for r in results:
    for c in r["claims"]:
        if c["flagged"]:
            cause_counts[c["cause"]] = cause_counts.get(c["cause"], 0) + 1
            all_entailments_flagged.append(c["entailment"])
        else:
            all_entailments_safe.append(c["entailment"])

print("Flagged claim causes:")
for cause, n in sorted(cause_counts.items(), key=lambda x: -x[1]):
    print(f"  {cause}: {n}")
print()

def pct(lst, lo, hi):
    return sum(1 for x in lst if lo <= x < hi)

bins = [(0.0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01)]
print("Entailment score distribution — FLAGGED claims:")
for lo, hi in bins:
    n = pct(all_entailments_flagged, lo, hi)
    print(f"  [{lo:.1f}, {hi:.2f}): {n}")
print(f"  total flagged claims: {len(all_entailments_flagged)}")
print()

print("Entailment score distribution — not-flagged claims (reference):")
for lo, hi in bins:
    n = pct(all_entailments_safe, lo, hi)
    print(f"  [{lo:.1f}, {hi:.2f}): {n}")
print(f"  total safe claims: {len(all_entailments_safe)}")
print()

# Answer-level claim count distribution
from collections import Counter
nc_dist = Counter(r["n_claims"] for r in results)
print("Claims per answer distribution (all clean answers):")
for k in sorted(nc_dist):
    print(f"  {k} claims: {nc_dist[k]} answers")
print()

# Per-phenomenon breakdown
print("Altered by phenomenon:")
from collections import defaultdict
by_phenom: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "altered": 0})
for r in results:
    ph = r["phenomenon"]
    by_phenom[ph]["total"] += 1
    if r["answer_altered"]:
        by_phenom[ph]["altered"] += 1
for ph, v in sorted(by_phenom.items()):
    print(f"  {ph}: {v['altered']}/{v['total']}")
print()

# Specific examples: show first 3 altered answers with claim details
print("=== EXAMPLE ALTERED CLEAN ANSWERS ===\n")
shown = 0
for r in results:
    if not r["answer_altered"]:
        continue
    print(f"ID={r['id']} phenomenon={r['phenomenon']} test_focus={r['test_focus']}")
    print(f"  Answer: {r['answer'][:200]}")
    print(f"  Context: {r['context'][0][:200] if r['context'] else '(none)'}")
    print(f"  N claims: {r['n_claims']}, N flagged: {r['n_flagged']}")
    for c in r["claims"]:
        flag_marker = "*** FLAGGED" if c["flagged"] else "    ok"
        print(f"  {flag_marker} | cause={c['cause']} | E={c['entailment']:.3f} N={c['neutral']:.3f} C={c['contradiction']:.3f}")
        print(f"           claim: {c['claim'][:150]}")
        if c["claim_vals"]:
            print(f"           typed vals: {c['claim_vals']}")
        print(f"           passage[{c['n_active_passages']}]: {c['selected_passage'][:120]}")
    print()
    shown += 1
    if shown >= 5:
        break
