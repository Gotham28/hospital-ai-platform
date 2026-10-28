import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

import json
from backend.research.guard.nli import _decompose_passages, _select_candidate_passages, _typed_values

data = json.load(open('backend/research/results/guard-parser-v5-2026-10-28/diagnose_details.json'))

print(f"Total flagged claims across 399 clean answers: {len(data)}")

# Let's inspect diverse failure types:
# 1. Exact numeric override when entailment was high (Hypothesis 1)
numeric_overrides = [d for d in data if d["exact_verdict"] == "contradicted"]
print(f"Exact contradicted overrides: {len(numeric_overrides)}")

# 2. Extreme threshold (0.50 <= entailment < 0.90)
threshold_kills = [d for d in data if 0.50 <= d["scores"]["entailment"] < 0.90 and d["exact_verdict"] is None and d["scores"]["contradiction"] < 0.30]
print(f"Pure threshold kills (0.50 <= ent < 0.90, con < 0.30): {len(threshold_kills)}")

# 3. Pronoun / anaphora claims (claims starting with it, he, she, they)
pronoun_claims = [d for d in data if d["text"].lower().startswith(("it ", "it's ", "they ", "he ", "she ", "this ", "these "))]
print(f"Pronoun-headed claims: {len(pronoun_claims)}")

# 4. Pure neutral (neutral >= 0.70, con < 0.10)
pure_neutrals = [d for d in data if d["scores"]["neutral"] >= 0.70 and d["scores"]["contradiction"] < 0.10]
print(f"Pure neutral claims: {len(pure_neutrals)}")

# 5. High contradiction (con >= 0.80) on clean answers
high_con = [d for d in data if d["scores"]["contradiction"] >= 0.80]
print(f"High contradiction claims (con >= 0.80): {len(high_con)}")

# Let's inspect some of each and print full context
examples = []

# Take 3 numeric overrides
for d in numeric_overrides[:4]:
    examples.append(("numeric_override", d))

# Take 3 pure threshold kills
for d in threshold_kills[:4]:
    examples.append(("extreme_threshold", d))

# Take 3 pronoun / clause split issues
for d in pronoun_claims[:4]:
    examples.append(("pronoun_clause_split", d))

# Take 3 high contradictions on clean answers
for d in high_con[:4]:
    examples.append(("high_contradiction_passage_miss", d))

print(f"\nCollected {len(examples)} detailed examples. Printing...")

output_rows = []
for cat, ex in examples:
    # Get active passages
    active = _select_candidate_passages(ex["text"], _decompose_passages(ex["context"]), max_candidates=4)
    claim_val = _typed_values(ex["text"])
    passage_vals = [_typed_values(p) for p in active]
    
    row = {
        "category": cat,
        "id": ex["id"],
        "task": ex["task"],
        "claim": ex["text"],
        "scores": ex["scores"],
        "verdict": ex["verdict"],
        "exact_verdict": ex["exact_verdict"],
        "claim_values": {k: list(v) for k, v in claim_val.items() if v},
        "active_passages": active,
        "all_context_passages": ex["context"],
        "full_response": ex["response"]
    }
    output_rows.append(row)

Path("backend/research/results/guard-parser-v5-2026-10-28/selected_examples.json").write_text(json.dumps(output_rows, indent=2), encoding="utf-8")
print("Saved to selected_examples.json.")
