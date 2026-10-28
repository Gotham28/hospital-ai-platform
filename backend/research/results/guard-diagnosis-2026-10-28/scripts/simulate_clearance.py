import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

import json
from backend.research.guard.action_policy import should_alter, ActionPolicy, BASELINE

# Load traces
traces = [json.loads(line) for line in Path("backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl").read_text(encoding="utf-8").splitlines()]
clean_traces = [t for t in traces if not t["gold_spans"]]
print(f"Total clean traces: {len(clean_traces)}")

# Baseline:
# An answer is altered if any claim has verdict in {'unsupported', 'contradicted'}
baseline_altered = sum(1 for t in clean_traces if any(c["verdict"] in {"unsupported", "contradicted"} for c in t["claims"]))
print(f"Baseline clean altered: {baseline_altered} / {len(clean_traces)}")

# Simulation 1: Fix Extreme Threshold (Entailment >= 0.50 is supported, unless contradiction >= 0.30 or exact)
def sim_threshold_050(t):
    for c in t["claims"]:
        e = c["scores"]["entailment"]
        con = c["scores"]["contradiction"]
        exact = c["exact_verdict"]
        # re-evaluate verdict with threshold 0.50 instead of 0.90
        if exact is not None:
            v = exact
        elif con >= 0.30 and con > e:
            v = "contradicted"
        elif e >= 0.50:
            v = "supported"
        else:
            v = "unsupported"
        if v in {"unsupported", "contradicted"}:
            return True # altered
    return False

sim1_altered = sum(1 for t in clean_traces if sim_threshold_050(t))
print(f"Fix Threshold to 0.50 alone: altered = {sim1_altered} / {len(clean_traces)} (clears {baseline_altered - sim1_altered} answers)")

# Simulation 2: Fix Numeric Disjoint Override Bug alone (ignore exact_verdict when exact == 'contradicted' if e >= 0.50)
def sim_numeric_fix_alone(t):
    for c in t["claims"]:
        e = c["scores"]["entailment"]
        con = c["scores"]["contradiction"]
        # original thresholds (0.90), but exact numeric override cannot override when e >= 0.50
        exact = c["exact_verdict"]
        if exact == "contradicted" and e >= 0.50:
            exact = None
        if exact is not None:
            v = exact
        elif con >= 0.30 and con > e:
            v = "contradicted"
        elif e >= 0.90:
            v = "supported"
        else:
            v = "unsupported"
        if v in {"unsupported", "contradicted"}:
            return True
    return False

sim2_altered = sum(1 for t in clean_traces if sim_numeric_fix_alone(t))
print(f"Fix Numeric Override alone: altered = {sim2_altered} / {len(clean_traces)} (clears {baseline_altered - sim2_altered} answers)")

# Simulation 3: Action Policy ntoff alone (ct0.5_ntoff: only contradiction alters, neutral does not)
# From development-metrics.json:
sim3_altered = 271
print(f"Action Policy ct0.5_ntoff alone: altered = {sim3_altered} / {len(clean_traces)} (clears {baseline_altered - sim3_altered} answers)")

sim3b_altered = 247
print(f"Action Policy ct0.7_ntoff alone: altered = {sim3b_altered} / {len(clean_traces)} (clears {baseline_altered - sim3b_altered} answers)")

sim3c_altered = 198
print(f"Action Policy ct0.9_ntoff alone: altered = {sim3c_altered} / {len(clean_traces)} (clears {baseline_altered - sim3c_altered} answers)")

# Simulation 4: Combined Threshold 0.50 + Action Policy ct0.5_ntoff
def sim_combined(t, c_thresh=0.5):
    for c in t["claims"]:
        e = c["scores"]["entailment"]
        con = c["scores"]["contradiction"]
        # With threshold 0.50 and action policy requiring contradiction >= c_thresh
        if con >= c_thresh and con > e:
            return True # altered
    return False

sim4_altered = sum(1 for t in clean_traces if sim_combined(t, 0.5))
print(f"Combined Threshold 0.50 + Action Policy con>=0.5 alone: altered = {sim4_altered} / {len(clean_traces)} (clears {baseline_altered - sim4_altered} answers)")

sim4b_altered = sum(1 for t in clean_traces if sim_combined(t, 0.7))
print(f"Combined Threshold 0.50 + Action Policy con>=0.7 alone: altered = {sim4b_altered} / {len(clean_traces)} (clears {baseline_altered - sim4b_altered} answers)")
