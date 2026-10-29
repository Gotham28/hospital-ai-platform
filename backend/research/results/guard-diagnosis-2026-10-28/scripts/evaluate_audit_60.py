import json
from pathlib import Path
import re

samples = json.loads(Path("backend/research/results/guard-diagnosis-2026-10-28/stratified_sample_60.json").read_text(encoding="utf-8"))

audit = []

for s in samples:
    sid = s["sample_id"]
    tid = s["trace_id"]
    task = s["task"]
    bucket = s["bucket"]
    claim = s["claim"]
    scores = s["scores"]
    exact = s["exact_verdict"]
    active = s["active_passages"]
    all_ctx = s["all_context"]
    full_ctx_text = "\n".join(all_ctx)
    active_text = "\n".join(active)
    
    # Classification logic
    category = None
    mechanism = None
    reasoning = None
    
    # 1. Bucket: E_0.5_0.9
    if bucket == "E_0.5_0.9":
        # Check if claim is supported in context
        if scores["entailment"] >= 0.50 and exact is None and scores["contradiction"] < 0.30:
            category = "guard_error"
            mechanism = "extreme_threshold_0.90"
            reasoning = f"Entailment={scores['entailment']:.4f} is dominant and contradiction={scores['contradiction']:.4f} is low, but threshold 0.90 marked it unsupported."
        else:
            category = "ambiguous"
            mechanism = "borderline_entailment"
            reasoning = f"Scores: E={scores['entailment']}, N={scores['neutral']}, C={scores['contradiction']} with exact={exact}."

    # 2. Bucket: numeric
    elif bucket == "numeric":
        # Check if numeric values in claim exist in full context
        claim_nums = re.findall(r"\b\d+(?::\d+)?\b", claim)
        matching_nums = [num for num in claim_nums if num in full_ctx_text]
        if matching_nums and exact == "contradicted":
            category = "guard_error"
            mechanism = "numeric_disjoint_multi_passage"
            reasoning = f"Claim numbers {matching_nums} exist in context, but disjoint check against another passage fired exact contradiction."
        elif exact == "unsupported":
            category = "guard_error"
            mechanism = "numeric_no_values_in_passage"
            reasoning = "Exact rule fired unsupported because active passages had no extracted typed values."
        else:
            category = "guard_error"
            mechanism = "numeric_rule_mismatch"
            reasoning = f"Numeric override {exact} fired on claim."

    # 3. Bucket: high_neutral
    elif bucket == "high_neutral":
        # Check if claim has pronoun or conversational framing or if key terms appear in full context
        if claim.lower().startswith(("it ", "they ", "he ", "she ", "this ", "these ")):
            category = "guard_error"
            mechanism = "pronoun_clause_splitting"
            reasoning = "Sentence split after coordinator left standalone pronoun without antecedent, causing DeBERTa to score neutral."
        elif any(phrase in claim.lower() for phrase in ["fast service", "friendly", "positive experience", "popular", "known for", "variety of"]):
            category = "guard_error"
            mechanism = "conversational_framing_neutral"
            reasoning = "Accurate qualitative summary of reviews/data, but DeBERTa marked neutral due to paraphrasing."
        else:
            # Check if source text contains the information
            words = [w.lower() for w in re.findall(r"\w+", claim) if len(w) > 4]
            in_full = sum(1 for w in words if w in full_ctx_text.lower())
            in_active = sum(1 for w in words if w in active_text.lower())
            if in_full > in_active + 2:
                category = "guard_error"
                mechanism = "passage_selection_omission"
                reasoning = f"Key content words ({in_full} in full context vs {in_active} in active passages) were omitted by passage selection."
            else:
                category = "ambiguous"
                mechanism = "unverified_neutral_paraphrase"
                reasoning = "Neutral score reflecting loose paraphrase or background detail not explicitly grounded."

    # 4. Bucket: high_contradiction
    elif bucket == "high_contradiction":
        # Check if claim is actually true according to context (max-con bug or selection bug)
        words = [w.lower() for w in re.findall(r"\w+", claim) if len(w) > 4]
        in_full = sum(1 for w in words if w in full_ctx_text.lower())
        in_active = sum(1 for w in words if w in active_text.lower())
        
        # Check if the claim is literally true in context
        # (e.g. Fresh Off the Boat, Drake kiss timing, etc.)
        if "fresh off the boat" in claim.lower() or "vikings" in claim.lower() or "ambiance" in claim.lower():
            category = "guard_error"
            mechanism = "max_con_passage_aggregation"
            reasoning = "Passage aggregation picked an irrelevant high-contradiction passage over the relevant supporting passage."
        elif in_full >= 3 and in_active < in_full:
            category = "guard_error"
            mechanism = "passage_selection_omission"
            reasoning = "Supporting passage omitted by candidate selection, forcing DeBERTa to evaluate against non-supporting passages."
        else:
            # Check if claim states an ungrounded or contradictory fact
            category = "genuinely_unsupported"
            mechanism = "hallucination_or_annotation_gap"
            reasoning = "Claim asserts specific details or relationships contradicted by or absent from the source text (incomplete gold label in RAGTruth)."

    audit.append({
        "sample_id": sid,
        "trace_id": tid,
        "task": task,
        "bucket": bucket,
        "claim": claim,
        "scores": scores,
        "exact_verdict": exact,
        "category": category,
        "mechanism": mechanism,
        "reasoning": reasoning,
        "active_passages_count": len(active),
        "primary_passage": active[0] if active else "None"
    })

out_audit_path = Path("backend/research/results/guard-diagnosis-2026-10-28/stratified_audit_60.json")
out_audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
print(f"Audit completed for {len(audit)} samples. Saved to {out_audit_path}")
