import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))
from backend.research.guard.nli import MultilingualNLIScorer, _decompose_passages, _select_candidate_passages
from backend.research.run_guard_calibration import load_inputs, selected_items

manifest, responses = load_inputs()
dev_items = {item['id']: item for item in selected_items(manifest, responses, 'development')}
item = dev_items['12426']
passages = _decompose_passages(item['context'])

scorer_b1 = MultilingualNLIScorer(device='cpu', batch_size=1)
scorer_b8 = MultilingualNLIScorer(device='cpu', batch_size=8)
scorer_b16 = MultilingualNLIScorer(device='cpu', batch_size=16)

unrelated_pairs = [('The hospital is located in Kochi.', 'The hospital is in Kerala.')] * 20

for cidx, claim_text in [(2, 'the minimum temperature can go down to 58\u2109.'), (4, 'the minimum temperature is approximately 35\u2109.')]:
    candidates = _select_candidate_passages(claim_text, passages, max_candidates=4)
    target_pairs = [(p, claim_text) for p in candidates]
    
    # Way A: batch size 1
    scores_a = [scorer_b1.score_pairs([p])[0] for p in target_pairs]
    # Way B: one call of len(candidates)
    scores_b = scorer_b8.score_pairs(target_pairs)
    # Way C: inside batch of 16 padded with unrelated pairs
    padded = target_pairs + unrelated_pairs[:16 - len(target_pairs)]
    scores_c = scorer_b16.score_pairs(padded)[:len(target_pairs)]
    
    print(f"\n=== Claim {cidx}: {claim_text} ===")
    max_d_claim = 0.0
    for pi, p in enumerate(candidates):
        sa, sb, sc = scores_a[pi], scores_b[pi], scores_c[pi]
        diff_ab = max(abs(sa.entailment - sb.entailment), abs(sa.neutral - sb.neutral), abs(sa.contradiction - sb.contradiction))
        diff_bc = max(abs(sb.entailment - sc.entailment), abs(sb.neutral - sc.neutral), abs(sb.contradiction - sc.contradiction))
        diff_ac = max(abs(sa.entailment - sc.entailment), abs(sa.neutral - sc.neutral), abs(sa.contradiction - sc.contradiction))
        max_d = max(diff_ab, diff_bc, diff_ac)
        if max_d > max_d_claim:
            max_d_claim = max_d
        print(f"Passage {pi} ({repr(p[:50])}...):")
        print(f"  Way A (bs=1) : E={sa.entailment:.8f}, N={sa.neutral:.8f}, C={sa.contradiction:.8f}")
        print(f"  Way B (call) : E={sb.entailment:.8f}, N={sb.neutral:.8f}, C={sb.contradiction:.8f}")
        print(f"  Way C (bs=16): E={sc.entailment:.8f}, N={sc.neutral:.8f}, C={sc.contradiction:.8f}")
        print(f"  Max diff between ways: {max_d:.8e}")
    print(f"Max difference across ways for Claim {cidx}: {max_d_claim:.8e}")
