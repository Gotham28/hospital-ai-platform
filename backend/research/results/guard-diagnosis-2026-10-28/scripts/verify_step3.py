import sys
import json
from pathlib import Path

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from backend.research.guard.claims import split_claims
from backend.research.guard.guard import _thresholds
from backend.research.guard.action_policy import BASELINE, should_alter
from backend.research.guard.eval_external import removal_mask
from backend.research.replay.cache import NLICache
from backend.research.replay.scorer import CachedScorer
from backend.research.run_guard_calibration import load_inputs, selected_items, score_policy, metrics

manifest, responses = load_inputs()
dev_items = {item['id']: item for item in selected_items(manifest, responses, 'development')}

cache_path = repo_root / 'backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl'
cache = NLICache(cache_path)
scorer = CachedScorer(cache, mode='strict')
_, thresholds = _thresholds('en')

traces_path = repo_root / 'backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl'
stored_traces = [json.loads(line) for line in traces_path.read_text(encoding='utf-8').splitlines()]
stored_by_id = {str(t['id']): t for t in stored_traces}
base_eval_rows = [score_policy(item, stored_by_id[str(item['id'])], BASELINE) for item in dev_items.values()]
ref_base_ids = {r['id'] for r in base_eval_rows if r['gold_error'] and r['spans']['fully_intercepted']}

traces = []
for item_id, item in dev_items.items():
    raw_claims = split_claims(item['answer'], lang=item['lang'])
    re_claims = []
    for c in raw_claims:
        assessment = scorer.assess(
            c,
            item['context'],
            entailment_threshold=thresholds.entailment,
            contradiction_threshold=thresholds.contradiction,
        )
        re_claims.append({
            'text': c,
            'verdict': assessment.verdict,
            'exact_verdict': assessment.exact_verdict,
            'scores': vars(assessment.scores),
        })
    traces.append({
        'id': item_id,
        'task': item['task'],
        'quality': item['quality'],
        'gold_spans': item.get('gold_spans', []),
        'claims': re_claims,
        'answer': item['answer'],
        'context': item['context'],
        'inference_seconds': 0.0,
    })

by_id = {str(t['id']): t for t in traces}
eval_rows = [score_policy(item, by_id[item['id']], BASELINE) for item in dev_items.values()]
m = metrics(eval_rows, include_subgroups=False)

inter_ids = {r['id'] for r in eval_rows if r['gold_error'] and r['spans']['fully_intercepted']}
lost_ids = sorted(list(ref_base_ids - inter_ids), key=int)

print(f"Clean altered: {m['false_alterations']}/{m['clean']}")
print(f"Intercepted  : {m['fully_intercepted']}/{m['erroneous']}")
print(f"Char prec    : {m['character_precision']:.4f}")
print(f"Lost IDs     : {lost_ids}")
