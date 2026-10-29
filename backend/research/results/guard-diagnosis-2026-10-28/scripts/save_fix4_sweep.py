import sys
import json
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

from tune_sweep import eval_fn, all_groups, rng, tune_g, check_g

sweep_data = {
    "split_info": {
        "seed": 20261028,
        "total_groups": 120,
        "tune_groups_count": 60,
        "check_groups_count": 60,
    },
    "tune_090_reference": {},
    "check_090_reference": {},
    "combined_090_reference": {},
    "rows": []
}

# Reference 0.90 values
m_tune_090 = eval_fn(0.90, tune_g)
m_check_090 = eval_fn(0.90, check_g)
m_comb_090 = eval_fn(0.90, None)

sweep_data["tune_090_reference"] = {
    "clean_altered": m_tune_090["false_alterations"],
    "clean_count": m_tune_090["clean"],
    "clean_altered_pct": round(m_tune_090["false_alterations"] / m_tune_090["clean"] * 100, 2),
    "intercepted": m_tune_090["fully_intercepted"],
    "erroneous_count": m_tune_090["erroneous"],
    "intercepted_pct": round(m_tune_090["fully_intercepted"] / m_tune_090["erroneous"] * 100, 2),
    "char_precision": round(m_tune_090["character_precision"], 4),
}

sweep_data["check_090_reference"] = {
    "clean_altered": m_check_090["false_alterations"],
    "clean_count": m_check_090["clean"],
    "clean_altered_pct": round(m_check_090["false_alterations"] / m_check_090["clean"] * 100, 2),
    "intercepted": m_check_090["fully_intercepted"],
    "erroneous_count": m_check_090["erroneous"],
    "intercepted_pct": round(m_check_090["fully_intercepted"] / m_check_090["erroneous"] * 100, 2),
    "char_precision": round(m_check_090["character_precision"], 4),
}

sweep_data["combined_090_reference"] = {
    "clean_altered": m_comb_090["false_alterations"],
    "clean_count": m_comb_090["clean"],
    "clean_altered_pct": round(m_comb_090["false_alterations"] / m_comb_090["clean"] * 100, 2),
    "intercepted": m_comb_090["fully_intercepted"],
    "erroneous_count": m_comb_090["erroneous"],
    "intercepted_pct": round(m_comb_090["fully_intercepted"] / m_comb_090["erroneous"] * 100, 2),
    "char_precision": round(m_comb_090["character_precision"], 4),
}

for ethresh in [round(0.50 + 0.05 * i, 2) for i in range(9)]:
    m_tune = eval_fn(ethresh, tune_g)
    m_check = eval_fn(ethresh, check_g)
    m_comb = eval_fn(ethresh, None)
    
    tune_ca_pct = m_tune["false_alterations"] / m_tune["clean"] * 100
    tune_int_pct = m_tune["fully_intercepted"] / m_tune["erroneous"] * 100
    check_ca_pct = m_check["false_alterations"] / m_check["clean"] * 100
    check_int_pct = m_check["fully_intercepted"] / m_check["erroneous"] * 100
    comb_ca_pct = m_comb["false_alterations"] / m_comb["clean"] * 100
    comb_int_pct = m_comb["fully_intercepted"] / m_comb["erroneous"] * 100
    
    disagreement_pct = abs(tune_int_pct - check_int_pct)
    
    # Deltas from each half's own 0.90 value
    delta_tune_ca = m_tune["false_alterations"] - m_tune_090["false_alterations"]
    delta_tune_int = m_tune["fully_intercepted"] - m_tune_090["fully_intercepted"]
    delta_tune_int_pct = tune_int_pct - sweep_data["tune_090_reference"]["intercepted_pct"]
    
    delta_check_ca = m_check["false_alterations"] - m_check_090["false_alterations"]
    delta_check_int = m_check["fully_intercepted"] - m_check_090["fully_intercepted"]
    delta_check_int_pct = check_int_pct - sweep_data["check_090_reference"]["intercepted_pct"]
    
    delta_comb_ca = m_comb["false_alterations"] - m_comb_090["false_alterations"]
    delta_comb_int = m_comb["fully_intercepted"] - m_comb_090["fully_intercepted"]
    delta_comb_int_pct = comb_int_pct - sweep_data["combined_090_reference"]["intercepted_pct"]
    
    row = {
        "entailment_threshold": ethresh,
        "tune": {
            "clean_altered": f"{m_tune['false_alterations']}/{m_tune['clean']}",
            "clean_altered_pct": round(tune_ca_pct, 2),
            "intercepted": f"{m_tune['fully_intercepted']}/{m_tune['erroneous']}",
            "intercepted_pct": round(tune_int_pct, 2),
            "char_precision": round(m_tune["character_precision"], 4),
            "delta_from_090_clean_altered": delta_tune_ca,
            "delta_from_090_intercepted": delta_tune_int,
            "delta_from_090_intercepted_pct": round(delta_tune_int_pct, 2),
        },
        "check": {
            "clean_altered": f"{m_check['false_alterations']}/{m_check['clean']}",
            "clean_altered_pct": round(check_ca_pct, 2),
            "intercepted": f"{m_check['fully_intercepted']}/{m_check['erroneous']}",
            "intercepted_pct": round(check_int_pct, 2),
            "char_precision": round(m_check["character_precision"], 4),
            "delta_from_090_clean_altered": delta_check_ca,
            "delta_from_090_intercepted": delta_check_int,
            "delta_from_090_intercepted_pct": round(delta_check_int_pct, 2),
        },
        "disagreement_pct": round(disagreement_pct, 2),
        "combined": {
            "clean_altered": f"{m_comb['false_alterations']}/{m_comb['clean']}",
            "clean_altered_pct": round(comb_ca_pct, 2),
            "intercepted": f"{m_comb['fully_intercepted']}/{m_comb['erroneous']}",
            "intercepted_pct": round(comb_int_pct, 2),
            "char_precision": round(m_comb["character_precision"], 4),
            "delta_from_090_clean_altered": delta_comb_ca,
            "delta_from_090_intercepted": delta_comb_int,
            "delta_from_090_intercepted_pct": round(delta_comb_int_pct, 2),
        }
    }
    sweep_data["rows"].append(row)

out_file = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/fix4_threshold_sweep.json"
out_file.write_text(json.dumps(sweep_data, indent=2), encoding="utf-8")
print(f"Successfully saved Fix 4 sweep to {out_file}")
