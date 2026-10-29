import json
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

# 1. Print policy grid table from development-metrics.json
metrics_path = Path("backend/research/results/guard-parser-v5-2026-10-28/development-metrics.json")
metrics = json.loads(metrics_path.read_text(encoding="utf-8"))["results"]

print("="*80)
print("POLICY GRID: development-metrics.json (v5)")
print("="*80)
header = f"{'Policy':<15} | {'Clean Altered (/399)':<22} | {'Erroneous Intercepted (/321)':<30} | {'Char Precision':<15}"
print(header)
print("-" * len(header))

for name, res in metrics.items():
    clean_alt = f"{res['false_alterations']}/399 ({res['false_alteration_rate']*100:.1f}%)"
    err_int = f"{res['fully_intercepted']}/321 ({res['fully_intercepted_rate']*100:.1f}%)"
    char_prec = f"{res['character_precision']*100:.2f}%"
    print(f"{name:<15} | {clean_alt:<22} | {err_int:<30} | {char_prec:<15}")

# 2. Check gold span label types from rag-response.jsonl
rag_resp_path = Path("backend/research/results/guard-external-2026-10-26/data/rag-response.jsonl")
rag_data = {}
with open(rag_resp_path, "r", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        rag_data[str(r["id"])] = r

# Load traces
traces_path = Path("backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl")
traces = [json.loads(line) for line in traces_path.read_text(encoding="utf-8").splitlines()]

# For baseline and ct0.7_ntoff, simulate removal mask and check span interception by label_type
from backend.research.guard.action_policy import ActionPolicy, should_alter

policy_baseline = ActionPolicy("baseline", None, None, None, True)
policy_ct07 = ActionPolicy("ct0.7_ntoff", 0.7, None, None, False)

class SimpleScores:
    def __init__(self, d):
        self.entailment = d["entailment"]
        self.neutral = d["neutral"]
        self.contradiction = d["contradiction"]

def get_removed_indices(answer, claims, policy):
    text = answer
    indices = list(range(len(answer)))
    removed = set()
    for c in claims:
        scores = SimpleScores(c["scores"])
        action = should_alter(c["verdict"], scores, c["exact_verdict"], policy)
        if not action:
            continue
        target = c["text"]
        cursor = 0
        while (start := text.find(target, cursor)) >= 0:
            end = start + len(target)
            removed.update(i for i in indices[start:end] if i is not None)
            text = text[:start] + "[FLAG_TEXT]" + text[end:]
            indices[start:end] = [None] * len("[FLAG_TEXT]")
            cursor = start + len("[FLAG_TEXT]")
    return removed

# Count spans by label_type and their interception
total_spans = defaultdict(int)
intercepted_baseline = defaultdict(int)
intercepted_ct07 = defaultdict(int)

# Also count response-level full interception by label_type dominance
resp_has_type = defaultdict(int)
resp_fully_int_baseline = defaultdict(int)
resp_fully_int_ct07 = defaultdict(int)

for t in traces:
    tid = str(t["id"])
    if tid not in rag_data:
        continue
    r_item = rag_data[tid]
    answer = r_item["response"]
    labels = r_item.get("labels", [])
    if not labels:
        continue
    
    removed_base = get_removed_indices(answer, t["claims"], policy_baseline)
    removed_ct07 = get_removed_indices(answer, t["claims"], policy_ct07)
    
    for lbl in labels:
        l_type = lbl["label_type"]
        start, end = lbl["start"], lbl["end"]
        span_set = set(range(start, end))
        total_spans[l_type] += 1
        if span_set <= removed_base:
            intercepted_baseline[l_type] += 1
        if span_set <= removed_ct07:
            intercepted_ct07[l_type] += 1

print("\n" + "="*80)
print("SPAN INTERCEPTION BY LABEL TYPE: baseline vs ct0.7_ntoff")
print("="*80)
header2 = f"{'Label Type':<25} | {'Total Spans':<12} | {'Baseline Intercepted':<22} | {'ct0.7_ntoff Intercepted':<25}"
print(header2)
print("-" * len(header2))

for l_type in sorted(total_spans.keys()):
    tot = total_spans[l_type]
    base_cnt = intercepted_baseline[l_type]
    ct_cnt = intercepted_ct07[l_type]
    base_str = f"{base_cnt}/{tot} ({base_cnt/tot*100:.1f}%)"
    ct_str = f"{ct_cnt}/{tot} ({ct_cnt/tot*100:.1f}%)"
    print(f"{l_type:<25} | {tot:<12} | {base_str:<22} | {ct_str:<25}")
