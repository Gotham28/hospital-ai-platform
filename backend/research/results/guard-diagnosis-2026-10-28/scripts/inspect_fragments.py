import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
traces_path = repo_root / "backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl"
rows = [json.loads(line) for line in traces_path.read_text(encoding="utf-8").splitlines()]

all_claims = []
for r in rows:
    for ci, c in enumerate(r["claims"]):
        all_claims.append({
            "answer_id": r["id"],
            "quality": r["quality"],
            "claim_index": ci,
            "text": c["text"],
            "verdict": c["verdict"],
        })

print(f"Total claims: {len(all_claims)}")

# Look for patterns
# 1. Bare numbers / list markers like "3.", "1.", "2)", "Passage 1:", "Passage 2:"
# 2. Refusals like "Unable to answer based on given passages."
# 3. Conversational phrases like "Sure!", "Here is an objective overview..."

patterns = {
    "list_num": re.compile(r"^\s*(\d+|[a-zA-Z])[\.\)]\s*$"),
    "passage_header": re.compile(r"^\s*passage\s*\d+\s*:\s*$", re.IGNORECASE),
    "bare_refusal": re.compile(r"^\s*unable to answer based on (?:the )?given passages?\.?\s*$", re.IGNORECASE),
    "intro_sure": re.compile(r"^\s*sure\s*!*$", re.IGNORECASE),
    "overview_intro": re.compile(r"^\s*(?:here (?:is|are)|based on the provided).*(?:overview|summary|article|information).*:?\s*$", re.IGNORECASE),
}

matches_by_pattern = {k: [] for k in patterns}
for c in all_claims:
    t = c["text"].strip()
    for pname, pat in patterns.items():
        if pat.match(t):
            matches_by_pattern[pname].append(c)

print("\n--- Matches by Candidate Pattern ---")
for pname, mlist in matches_by_pattern.items():
    print(f"\nPattern '{pname}': {len(mlist)} claims")
    sample_texts = Counter([c["text"] for c in mlist])
    for text, cnt in sample_texts.most_common(5):
        print(f"  ({cnt}x) {repr(text)}")
    clean_count = sum(1 for c in mlist if c["quality"] == "clean")
    err_count = sum(1 for c in mlist if c["quality"] == "erroneous")
    print(f"  Distribution: {clean_count} clean, {err_count} erroneous")

# Check all claims with len < 15
print("\n--- Short claims (len <= 15) ---")
short_claims = [c for c in all_claims if len(c["text"].strip()) <= 15]
print(f"Count of claims len <= 15: {len(short_claims)}")
for text, cnt in Counter([c["text"].strip() for c in short_claims]).most_common(20):
    print(f"  ({cnt}x) {repr(text)}")
