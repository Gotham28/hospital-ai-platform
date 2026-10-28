"""Fill NLI cache for all unique pairs from development traces."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(".").resolve()))

import torch
from backend.research.guard.nli import MultilingualNLIScorer
from backend.research.replay.cache import DEFAULT_MODEL_REVISION, NLICache, make_key
from backend.research.replay.enumerate_pairs import enumerate_development_pairs

CACHE_PATH = Path("backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl")


def fill_cache(
    cache_path: Path = CACHE_PATH,
    *,
    batch_size: int = 16,
    flush_every: int = 500,
    log_every: int = 1000,
    num_threads: int = 4,
) -> None:
    torch.set_num_threads(num_threads)
    print(f"Configured torch.set_num_threads({num_threads})")

    # 1. Enumerate all unique pairs with metadata
    print("Enumerating development pairs...")
    unique_pairs: dict[str, dict] = {}
    for r in enumerate_development_pairs():
        if r.key not in unique_pairs:
            unique_pairs[r.key] = {
                "key": r.key,
                "passage": r.passage,
                "claim": r.claim,
                "answer_id": r.answer_id,
                "claim_index": r.claim_index,
                "passage_index": r.passage_index,
            }

    total_unique = len(unique_pairs)
    print(f"Total unique pairs to evaluate: {total_unique}")

    # 2. Initialize cache (resumable)
    cache = NLICache(cache_path, flush_every=flush_every)
    existing_count = len(cache)
    print(f"Existing cache records: {existing_count}")

    # 3. Filter remaining
    remaining = [v for k, v in unique_pairs.items() if k not in cache]
    print(f"Remaining pairs to score: {len(remaining)}")

    if not remaining:
        print("Cache is already fully populated!")
        return

    # Sort remaining by length: len(passage) + len(claim)
    remaining.sort(key=lambda x: len(x["passage"]) + len(x["claim"]))

    # 4. Initialize scorer (pinned model on CPU)
    print(f"Initializing MultilingualNLIScorer on CPU (batch_size={batch_size})...")
    scorer = MultilingualNLIScorer(device="cpu", batch_size=batch_size)

    # 5. Process in batches of batch_size
    print(f"Starting fill loop ({len(remaining)} pairs, flush every {flush_every}, log every {log_every})...")
    start_time = time.perf_counter()
    processed_count = 0

    for i in range(0, len(remaining), batch_size):
        chunk = remaining[i : i + batch_size]
        pairs_to_score = [(item["passage"], item["claim"]) for item in chunk]
        scores_list = scorer.score_pairs(pairs_to_score)

        for item, scores in zip(chunk, scores_list):
            cache.set(
                item["key"],
                scores,
                answer_id=item["answer_id"],
                claim_index=item["claim_index"],
                passage_index=item["passage_index"],
            )

        processed_count += len(chunk)

        if processed_count % log_every < batch_size or processed_count == len(remaining):
            elapsed = time.perf_counter() - start_time
            rate = processed_count / elapsed if elapsed > 0 else 0
            eta_sec = (len(remaining) - processed_count) / rate if rate > 0 else 0
            print(
                f"[{time.strftime('%H:%M:%S')}] Progress: {processed_count}/{len(remaining)} pairs "
                f"({processed_count / len(remaining) * 100:.1f}%) | "
                f"Elapsed: {elapsed:.1f}s ({elapsed / 60:.1f}m) | "
                f"Rate: {rate:.2f} pairs/s | "
                f"ETA: {eta_sec / 60:.1f}m",
                flush=True,
            )

    cache.flush()
    cache.close()
    total_elapsed = time.perf_counter() - start_time
    print(f"\nFill completed successfully in {total_elapsed:.1f}s ({total_elapsed / 60:.1f}m)!")


def report_cache_stats(cache_path: Path = CACHE_PATH) -> None:
    if not cache_path.exists():
        print(f"Cache file {cache_path} does not exist.")
        return

    line_count = 0
    unique_keys = set()
    sha256 = hashlib.sha256()

    with cache_path.open("rb") as f:
        for line in f:
            line_count += 1
            sha256.update(line)
            try:
                rec = json.loads(line.decode("utf-8"))
                unique_keys.add(rec["key"])
            except Exception:
                pass

    size_bytes = cache_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)

    print("=" * 60)
    print("NLI CACHE FINAL REPORT:")
    print("=" * 60)
    print(f"Path            : {cache_path}")
    print(f"Line count      : {line_count}")
    print(f"Unique keys     : {len(unique_keys)}")
    print(f"File size       : {size_bytes} bytes ({size_mb:.2f} MB)")
    print(f"SHA256          : {sha256.hexdigest().upper()}")


if __name__ == "__main__":
    fill_cache()
    report_cache_stats()
