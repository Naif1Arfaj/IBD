"""Classify IBD / No IBD for one person from the 10 input groups.

Usage:
  .venv/bin/python predict.py --json example_patient.json
  .venv/bin/python predict.py --interactive      # prompts per group; Enter = dataset default

In code:
  from predict import predict_ibd
  result = predict_ibd({...61 variables...})
"""
import argparse
import json
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

from explain import make_explainer, top_factors
from features import BINARY_01_COLS, FEATURES, ORDINAL, YES_NO, YES_NO_COLS, encode

ARTIFACT = Path(__file__).resolve().parent / "artifacts" / "model.joblib"


@lru_cache(maxsize=1)
def _load():
    bundle = joblib.load(ARTIFACT)
    return bundle, make_explainer(bundle["model"], bundle["background"])


def _tier(p, tiers):
    if p < tiers["Low"]:
        return "Low"
    return "Moderate" if p < tiers["Moderate"] else "High"


def predict_ibd(patient: dict, n_factors: int = 5) -> dict:
    bundle, explainer = _load()
    extra = set(patient) - set(FEATURES)
    if extra:
        raise ValueError(f"Unknown variable(s): {sorted(extra)}")
    X = encode(pd.DataFrame([patient]))
    p = float(bundle["model"].predict_proba(X)[0, 1])
    shap_row = explainer(X)[0]
    return {
        "prediction": "IBD" if p >= bundle["threshold"] else "No IBD",
        "probability": round(p, 4),
        "risk_tier": _tier(p, bundle["tiers"]),
        "threshold": round(bundle["threshold"], 4),
        "model": bundle["model_name"],
        "top_factors": top_factors(shap_row, X.iloc[0], k=n_factors),
        "disclaimer": bundle["disclaimer"],
    }


def _allowed(col):
    if col in ORDINAL:
        return list(ORDINAL[col])
    if col in YES_NO_COLS:
        return list(YES_NO)
    if col in BINARY_01_COLS:
        return ["0", "1"]
    return None


def _interactive():
    bundle, _ = _load()
    patient = {}
    print("Enter each value (press Enter to use the dataset default shown in brackets).\n")
    for group, cols in bundle["groups"].items():
        print(f"== {group} ==")
        for col in cols:
            default = bundle["defaults"][col]
            opts = _allowed(col)
            hint = f" options {opts}" if opts else ""
            while True:
                raw = input(f"  {col}{hint} [{default}]: ").strip()
                val = default if raw == "" else raw
                try:
                    encode_check = {**{c: bundle["defaults"][c] for c in FEATURES}, col: val}
                    encode(pd.DataFrame([encode_check]))
                    patient[col] = val
                    break
                except (ValueError, TypeError) as e:
                    print(f"    invalid: {e}")
    return patient


def _print(result):
    print(f"\nPrediction : {result['prediction']}")
    prob = f"{result['probability']:.1%}" if result["probability"] >= 0.001 else "<0.1%"
    print(f"Probability: {prob}   Risk tier: {result['risk_tier']}   "
          f"(decision threshold {result['threshold']:.1%})")
    print(f"Model      : {result['model']}")
    print("Top factors:")
    for f in result["top_factors"]:
        print(f"  - {f['variable']} = {f['value']}  → {f['effect']}  ({f['shap_log_odds']:+.3f})")
    print(f"\n⚠ {result['disclaimer']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--json", help="path to a JSON file with the 61 input variables")
    g.add_argument("--interactive", action="store_true", help="prompt for each variable")
    ap.add_argument("--raw", action="store_true", help="print the result as JSON")
    a = ap.parse_args()
    patient = json.loads(Path(a.json).read_text()) if a.json else _interactive()
    res = predict_ibd(patient)
    print(json.dumps(res, indent=2, ensure_ascii=False)) if a.raw else _print(res)
