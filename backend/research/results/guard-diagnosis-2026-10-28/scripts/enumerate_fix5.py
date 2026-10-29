import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from backend.research.guard.claims import split_claims, _split_sentences
from backend.research.guard.nli import _select_candidate_passages, _decompose_passages
from backend.research.replay.cache import NLICache, make_key
from backend.research.run_guard_calibration import load_inputs, selected_items

cache_path = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl"
cache = NLICache(cache_path)

manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}

traces_path = repo_root / "backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl"
stored_by_id = {str(json.loads(line)["id"]): json.loads(line) for line in traces_path.read_text(encoding="utf-8").splitlines()}

# Proposed Fix 5 sentence-boundary chunker
def decompose_sentence_boundaries(passages: list[str]) -> list[str]:
    chunks = []
    for p in passages:
        sents = _split_sentences(p)
        buf, buf_len = [], 0
        for s in sents:
            s_clean = s.strip()
            if not s_clean:
                continue
            buf.append(s_clean)
            buf_len += len(s_clean)
            if buf_len >= 350:
                chunks.append(" ".join(buf))
                buf, buf_len = [], 0
        if buf:
            chunks.append(" ".join(buf))
    return chunks or passages

# Enumerate unique (passage, claim) pairs under Fix 5 (with Fix 3 split_claims)
all_pairs = set()
new_pairs = set()

for item_id, item in dev_items.items():
    claims = split_claims(item["answer"], lang=item["lang"])
    passages = decompose_sentence_boundaries(item["context"])
    
    for c in claims:
        candidates = _select_candidate_passages(c, passages, max_candidates=4)
        for p in candidates:
            k = make_key(p, c)
            all_pairs.add((p, c))
            if cache.get(k) is None:
                new_pairs.add((p, c))

total_pairs_count = len(all_pairs)
new_pairs_count = len(new_pairs)
already_cached = total_pairs_count - new_pairs_count

measured_s_per_pair = 0.42
projected_seconds = new_pairs_count * measured_s_per_pair
projected_hours = projected_seconds / 3600

print(f"Total unique (passage, claim) pairs: {total_pairs_count}")
print(f"Already in cache                   : {already_cached}")
print(f"New unique pairs to score          : {new_pairs_count}")
print(f"Measured rate                      : {measured_s_per_pair:.2f} s/pair")
print(f"Projected time                     : {projected_seconds:.1f} s ({projected_hours:.2f} hours)")
