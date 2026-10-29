import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))
p1_source = repo_root / "backend/research/results/guard-external-2026-10-26/data/rag-source.jsonl"
p1_response = repo_root / "backend/research/results/guard-external-2026-10-26/data/rag-response.jsonl"

p2_source = repo_root / "handoff/supplement/backend/research/results/guard-external-2026-10-26/data/rag-source.jsonl"
p2_response = repo_root / "handoff/supplement/backend/research/results/guard-external-2026-10-26/data/rag-response.jsonl"

def file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

print("=== DATASET FILE SHA256 COMPARISON ===")
s1_sha = file_sha256(p1_source)
s2_sha = file_sha256(p2_source)
print(f"guard-external rag-source.jsonl : {s1_sha}")
print(f"supplement     rag-source.jsonl : {s2_sha}")
print(f"Match: {s1_sha == s2_sha}")

r1_sha = file_sha256(p1_response)
r2_sha = file_sha256(p2_response)
print(f"guard-external rag-response.jsonl: {r1_sha}")
print(f"supplement     rag-response.jsonl: {r2_sha}")
print(f"Match: {r1_sha == r2_sha}")

# Also compare against development-manifest.json recorded hashes
manifest_path = repo_root / "backend/research/results/guard-action-policy-2026-10-27/development-manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
print(f"\nManifest recorded source_sha256    : {manifest.get('source_sha256')}")
print(f"Manifest source match: {s1_sha == manifest.get('source_sha256')}")
print(f"Manifest recorded responses_sha256 : {manifest.get('responses_sha256')}")
print(f"Manifest responses match: {r1_sha == manifest.get('responses_sha256')}")

# Now compare extracted context text for the 17 affected answers
census_path = Path("C:/Users/Sreehari/.gemini/antigravity-ide/brain/d3e4acec-ffb6-4824-b295-0bcf398df4e3/scratch/census_results.json")
census_data = json.loads(census_path.read_text(encoding="utf-8"))
affected_aids = sorted(list({c["answer_id"] for c in census_data["claims_above_1e4"]}), key=lambda x: int(x))
print(f"\n17 Affected Answer IDs: {affected_aids}")

from backend.research.run_guard_calibration import load_inputs, selected_items

m, r = load_inputs()
dev_items = {item["id"]: item for item in selected_items(m, r, "development")}

# Let's also load directly from p2
# We can load p2 sources and responses
source_p2 = {}
with open(p2_source, "r", encoding="utf-8") as f:
    for line in f:
        row = json.loads(line)
        source_p2[str(row["source_id"])] = row

resp_p2 = {}
with open(p2_response, "r", encoding="utf-8") as f:
    for line in f:
        row = json.loads(line)
        resp_p2[str(row["id"])] = row

from backend.research.guard.eval_external import adapt_ragtruth

print("\n--- Comparing context text character-by-character for 17 answers ---")
all_identical = True
for aid in affected_aids:
    ctx1 = dev_items[aid]["context"]
    resp_row = resp_p2[aid]
    source_row = source_p2[str(resp_row["source_id"])]
    item2 = adapt_ragtruth(resp_row, source_row, required_split="train")
    ctx2 = item2["context"]
    
    if ctx1 != ctx2:
        print(f"MISMATCH in context for answer {aid}!")
        all_identical = False
    else:
        # Check passage by passage, character by character
        assert len(ctx1) == len(ctx2)
        for p1, p2 in zip(ctx1, ctx2):
            assert p1 == p2
        print(f"Answer {aid}: context 100% identical ({len(ctx1)} passages)")

print(f"\nContext comparison result: All 17 answers have identical context: {all_identical}")
