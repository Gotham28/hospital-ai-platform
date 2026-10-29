"""
Pure-Python diagnostic (no model, no GPU):
Runs bundle v5 claim segmentation and exact typed-value logic on the
46 'supported' fixture answers.

Shows:
- Number of claims per answer
- Exact-verdict outcomes (what would fire BEFORE NLI)
- Typed value extracted from each claim
- Which context values are present/absent for comparison

Run from repo root:
  python -B "C:\Users\Sreehari\.gemini\antigravity-ide\brain\d3e4acec-ffb6-4824-b295-0bcf398df4e3\scratch\diagnose_exact.py"
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from collections import Counter

REPO = Path(__file__).resolve().parents[4]
BUNDLE = REPO / "handoff/bundle/GUARD_AI_HANDOFF/backend/research"
sys.path.insert(0, str(BUNDLE))

# Import bundle v5 code
from guard.nli import _typed_values, _decompose_passages, _select_candidate_passages
from guard.claims import split_claims

FIXTURE = REPO / "backend/research/fixtures/guard_dev_set.json"
records = json.loads(FIXTURE.read_text(encoding="utf-8"))
supported = [r for r in records if r["ground_truth"]["overall_verdict"] == "supported"]
print(f"Supported (clean-labeled) fixture answers: {len(supported)}")
print()

ENTAILMENT_THRESH = 0.9
CONTRADICTION_THRESH = 0.3

results = []
for rec in supported:
    answer = rec["answer"]
    context = rec["context"]
    lang = rec.get("lang", "en")
    claims = split_claims(answer, lang)

    claim_details = []
    for claim in claims:
        # Bundle v5: decompose then select top-4
        active = _select_candidate_passages(claim, _decompose_passages(context), max_candidates=4)
        claim_vals = _typed_values(claim)
        ctx_vals = [_typed_values(p) for p in active]

        # Exact contradiction check (first-disjoint-passage logic)
        exact_verdict = None
        exact_cause = None
        for kind, vals in claim_vals.items():
            if not vals:
                continue
            for pidx, (p, pv) in enumerate(zip(active, ctx_vals)):
                if pv[kind] and vals.isdisjoint(pv[kind]):
                    exact_verdict = "contradicted"
                    exact_cause = f"kind={kind} claim={sorted(vals)} passage_has={sorted(pv[kind])}"
                    break
            if exact_verdict:
                break

        # Exact unsupported check
        if not exact_verdict:
            if any(claim_vals.values()) and not any(
                v for pv in ctx_vals for v in pv.values()
            ):
                exact_verdict = "unsupported"
                exact_cause = f"claim_has_typed_vals={[k for k,v in claim_vals.items() if v]} but context_has_none"

        all_claim_vals = {k: sorted(v) for k, v in claim_vals.items() if v}
        all_ctx_vals = {k: sorted({vi for pv in ctx_vals for vi in pv[k]}) for k in ["price", "time", "duration"]}
        all_ctx_vals = {k: v for k, v in all_ctx_vals.items() if v}

        claim_details.append({
            "claim": claim,
            "exact_verdict": exact_verdict,
            "exact_cause": exact_cause,
            "claim_typed_vals": all_claim_vals,
            "context_typed_vals": all_ctx_vals,
            "n_active": len(active),
            "active_passages": [p[:120] for p in active],
        })

    has_exact_flag = any(c["exact_verdict"] is not None for c in claim_details)
    results.append({
        "id": rec["id"],
        "phenomenon": rec.get("phenomenon", ""),
        "test_focus": rec.get("test_focus", ""),
        "lang": lang,
        "answer": answer,
        "context": context,
        "n_claims": len(claims),
        "n_exact_flagged": sum(1 for c in claim_details if c["exact_verdict"] is not None),
        "has_exact_flag": has_exact_flag,
        "claims": claim_details,
    })

print("=== CLAIM COUNT DISTRIBUTION (clean answers) ===")
nc = Counter(r["n_claims"] for r in results)
for k in sorted(nc):
    print(f"  {k} claims: {nc[k]} answers")
print()

print("=== EXACT-VERDICT DISTRIBUTION ===")
ev = Counter()
for r in results:
    for c in r["claims"]:
        ev[c["exact_verdict"] or "none"] += 1
for k, v in sorted(ev.items(), key=lambda x: -x[1]):
    print(f"  exact_verdict={k}: {v} claims")
print()

print("=== ANSWERS WITH EXACT-VERDICT FLAGS (pre-NLI) ===")
flagged_exact = [r for r in results if r["has_exact_flag"]]
print(f"  {len(flagged_exact)}/{len(results)} clean answers have at least one exact-verdict flag\n")

print("=== TYPED VALUE CLASSIFICATION — ALL CLAIMS IN CLEAN ANSWERS ===")
tv_claims = 0
tv_types = Counter()
for r in results:
    for c in r["claims"]:
        if c["claim_typed_vals"]:
            tv_claims += 1
            for k in c["claim_typed_vals"]:
                tv_types[k] += 1
print(f"  Claims with any typed value extracted: {tv_claims}/{sum(r['n_claims'] for r in results)}")
for k, v in sorted(tv_types.items(), key=lambda x: -x[1]):
    print(f"    type={k}: {v} claims")
print()

print("=== EXAMPLE EXACT-FLAGGED CLAIMS ===")
shown = 0
for r in results:
    for c in r["claims"]:
        if c["exact_verdict"] and shown < 10:
            print(f"  ID={r['id']} phenomenon={r['phenomenon']} lang={r['lang']}")
            print(f"    Answer:  {r['answer'][:200]}")
            print(f"    Context: {r['context'][0][:200] if r['context'] else '(none)'}")
            print(f"    Claim:   {c['claim'][:150]}")
            print(f"    exact_verdict: {c['exact_verdict']}")
            print(f"    cause: {c['exact_cause']}")
            print(f"    claim_typed_vals: {c['claim_typed_vals']}")
            print(f"    context_typed_vals: {c['context_typed_vals']}")
            print()
            shown += 1

print("=== EXAMPLES WHERE ANSWER APPEARS FINE BUT EXACT-VERDICT FIRES ===")
shown = 0
for r in results:
    if not r["has_exact_flag"] and r["n_claims"] > 0:
        print(f"  ID={r['id']} phenomenon={r['phenomenon']} test_focus={r['test_focus']} [{r['n_claims']} claims, no exact flag]")
        for c in r["claims"]:
            print(f"    claim: {c['claim'][:120]}")
            print(f"    claim_vals: {c['claim_typed_vals']}  ctx_vals: {c['context_typed_vals']}")
        print()
        shown += 1
        if shown >= 5:
            break

print()
print("=== PER-PHENOMENON BREAKDOWN ===")
from collections import defaultdict
by_ph: dict[str, dict] = defaultdict(lambda: {"total": 0, "exact_flagged": 0})
for r in results:
    by_ph[r["phenomenon"]]["total"] += 1
    if r["has_exact_flag"]:
        by_ph[r["phenomenon"]]["exact_flagged"] += 1
for ph, v in sorted(by_ph.items()):
    print(f"  {ph}: exact_flagged={v['exact_flagged']}/{v['total']}")
