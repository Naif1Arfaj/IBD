"""Glue between the Django app, the ML model (predict.py / explain.py) and the RAG package."""
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import numpy as np
import pandas as pd

from features import (BINARY_01_COLS, DISCLAIMER, FEATURES, GROUPS, NO_NARRATE, ORDINAL, YES_NO, YES_NO_COLS,
                      encode, load_raw)
from predict import _load as load_model
from rag import evidence as ev
from rag import llm
from rag.index import embedder
from rag.index import load as load_index
from rag.queries import GROUP_LABELS, label, unit
from rag.retrieve import search

from .models import Assessment, EvidenceSummary, Report

N_REPORT_FACTORS = 5

NEXT_STEPS = {
    "High": ("High-risk patient → consider fecal calprotectin confirmation and GI referral according to clinical "
             "assessment and local protocol."),
    "Moderate": ("Moderate risk → consider fecal calprotectin testing, review red-flag symptoms and arrange "
                 "follow-up; escalate if symptoms persist."),
    "Low": "Low risk → routine follow-up; reassess if gastrointestinal symptoms or red flags develop.",
}

WORKFLOW = [
    ("Open Patient Profile", "Review demographics"),
    ("Collect / Enter Data", "Clinical, lifestyle, microbiome"),
    ("Run AI Risk Assessment", "ML model analysis"),
    ("Review Results", "Explainable factors"),
    ("Support Follow-up", "Referral / monitoring"),
]


# ---------- dataset reference values ----------

@lru_cache(maxsize=1)
def dataset_stats():
    raw = load_raw()
    stats = {}
    for c in FEATURES:
        if raw[c].dtype == object:
            continue
        col = raw[c].astype(float)
        stats[c] = {"min": float(col.min()), "max": float(col.max()), "p33": float(col.quantile(0.33)),
                    "p67": float(col.quantile(0.67)), "integer": bool((col == col.round()).all())}
    return stats


def choices_for(feature):
    if feature in ORDINAL:
        return list(ORDINAL[feature])
    if feature in YES_NO_COLS:
        return list(YES_NO)
    if feature in BINARY_01_COLS:
        return ["No", "Yes"]
    return None


def display_value(feature, value):
    if feature in BINARY_01_COLS:
        return "Yes" if str(value) in ("1", "1.0", "Yes") else "No"
    if isinstance(value, float):
        value = f"{value:g}"
    u = unit(feature)
    return f"{value} {u}".strip() if u and not choices_for(feature) else str(value)


def level(feature, value):
    """'low' / 'typical' / 'high' relative to the dataset's tertiles (for profile colouring)."""
    s = dataset_stats().get(feature)
    if s is None or value is None:
        return ""
    v = float(value)
    return "low" if v < s["p33"] else "high" if v > s["p67"] else "typical"


def grouped_data(data):
    return [{"group": g, "items": [{"feature": f, "label": label(f), "value": display_value(f, data.get(f))}
                                   for f in cols]} for g, cols in GROUPS.items()]


# ---------- assessment ----------

def _bars(items):
    top = max((abs(i["shap"]) for i in items), default=0) or 1.0
    for i in items:
        i["pct"] = max(4, round(100 * abs(i["shap"]) / top))
    return items


def run_assessment(patient, user=None):
    bundle, explainer = load_model()
    X = encode(pd.DataFrame([patient.data]))
    p = float(bundle["model"].predict_proba(X)[0, 1])
    shap_row = np.asarray(explainer(X)[0], dtype=float)
    contrib = dict(zip(FEATURES, shap_row))

    factors = [{"feature": f, "label": label(f), "value": display_value(f, patient.data.get(f)),
                "shap": round(float(v), 4), "direction": "raises" if v > 0 else "lowers"}
               for f, v in contrib.items() if f not in NO_NARRATE and abs(v) > 1e-9]
    factors.sort(key=lambda d: -abs(d["shap"]))
    groups = []
    for g, cols in GROUPS.items():
        v = sum(contrib[c] for c in cols if c not in NO_NARRATE)
        groups.append({"group": g, "label": GROUP_LABELS[g], "shap": round(float(v), 4),
                       "direction": "raises" if v > 0 else "lowers"})
    groups.sort(key=lambda d: -abs(d["shap"]))

    tiers = bundle["tiers"]
    tier = "Low" if p < tiers["Low"] else "Moderate" if p < tiers["Moderate"] else "High"
    return Assessment.objects.create(
        patient=patient, inputs=patient.data, probability=p,
        prediction="IBD" if p >= bundle["threshold"] else "No IBD", tier=tier, threshold=bundle["threshold"],
        factors=_bars(factors[:12]), group_factors=_bars(groups), model_name=bundle["model_name"],
        assessed_by=user if user and user.is_authenticated else None)


def model_card():
    bundle, _ = load_model()
    m = bundle["test_metrics"]
    return {"name": bundle["model_name"], "threshold": bundle["threshold"], "tiers": bundle["tiers"],
            "precision": m["precision"], "recall": m["recall"], "accuracy": m["accuracy"],
            "auc": m.get("ROC_AUC"), "specificity": m["specificity"], "n_features": len(FEATURES),
            "disclaimer": DISCLAIMER}


# ---------- evidence & report ----------

def _cached_evidence(feature, direction):
    """Cached literature summary, or None. Offline results are refreshed once an API key exists."""
    cached = EvidenceSummary.objects.filter(feature=feature, direction=direction).first()
    if cached and (cached.llm_used or not llm.available()):
        return {"text": cached.text, "references": cached.references, "llm_used": cached.llm_used, "notice": None}
    return None


def _fresh_evidence(feature, direction):
    """Network/LLM work only (safe to run in a thread; no DB access)."""
    res = ev.feature_evidence(feature, direction)
    return {"text": res["text"], "references": ev.serialize_refs(res["references"]),
            "llm_used": res["llm_used"], "notice": res["notice"]}


def _store_evidence(feature, direction, res):
    EvidenceSummary.objects.update_or_create(
        feature=feature, direction=direction,
        defaults={"text": res["text"], "references": res["references"], "llm_used": res["llm_used"]})


def cached_feature_evidence(feature, direction):
    res = _cached_evidence(feature, direction)
    if res is None:
        res = _fresh_evidence(feature, direction)
        _store_evidence(feature, direction, res)
    return res


def _summary(a):
    lines = [f"Patient {a.patient.patient_code}: age {a.inputs.get('age_years')}, {a.inputs.get('sex')}.",
             f"Model: {a.model_name}. Estimated IBD probability {a.probability:.0%} → {a.prediction}, "
             f"{a.tier} risk tier (decision threshold {a.threshold:.0%}).",
             "Top contributing factors (SHAP, log-odds):"]
    lines += [f"- {f['label']} = {f['value']}: {f['direction']} risk ({f['shap']:+.2f})"
              for f in a.factors[:N_REPORT_FACTORS]]
    return "\n".join(lines)


def _offline_narrative(a):
    top = a.factors[:N_REPORT_FACTORS]
    up = [f"{f['label']} ({f['value']})" for f in top if f["direction"] == "raises"]
    down = [f"{f['label']} ({f['value']})" for f in top if f["direction"] == "lowers"]
    text = (f"The model estimated an IBD probability of {a.probability:.0%}, placing this patient in the "
            f"{a.tier.lower()} risk tier (prediction: {a.prediction}). ")
    if up:
        text += "Factors increasing the estimate: " + ", ".join(up) + ". "
    if down:
        text += "Factors lowering the estimate: " + ", ".join(down) + ". "
    text += ("The research evidence for each factor is summarised below.\n\n" + NEXT_STEPS[a.tier] +
             " This is AI-supported risk stratification; clinical assessment and physician evaluation remain required.")
    return text


def build_report(assessment):
    top = assessment.factors[:N_REPORT_FACTORS]
    results = [_cached_evidence(f["feature"], f["direction"]) for f in top]
    missing = [i for i, r in enumerate(results) if r is None]
    if missing:  # LLM / retrieval calls in parallel; DB writes stay on this thread (SQLite)
        load_index(), embedder()  # initialise shared caches before threads use them
        with ThreadPoolExecutor(max_workers=len(missing)) as pool:
            fresh = list(pool.map(lambda i: _fresh_evidence(top[i]["feature"], top[i]["direction"]), missing))
        for i, res in zip(missing, fresh):
            results[i] = res
            _store_evidence(top[i]["feature"], top[i]["direction"], res)
    evidence = [{**f, **r} for f, r in zip(top, results)]
    notice = next((r["notice"] for r in results if r.get("notice")), "")

    narrative, narrative_refs, used = "", [], False
    if llm.available():
        blocks = [(f["feature"], f["direction"], search(ev.query(f["feature"]), k=4)) for f in top]
        out = ev.patient_narrative(_summary(assessment), blocks)
        if out:
            narrative, refs = out
            narrative_refs, used = ev.serialize_refs(refs), True
        else:
            notice = notice or "Claude was unavailable for the narrative; a template summary is shown."
    if not narrative:
        narrative = _offline_narrative(assessment)
    if not llm.available():
        notice = "Offline mode: no Anthropic API key configured, so evidence shows the most relevant passages."

    return Report.objects.create(assessment=assessment, narrative=narrative, narrative_refs=narrative_refs,
                                 evidence=evidence, llm_used=used or any(r["llm_used"] for r in results),
                                 notice=notice[:300])


def bibliography(report):
    seen, out = set(), []
    for block in [*report.evidence, {"references": report.narrative_refs}]:
        for r in block.get("references", []):
            key = (r["file"], r["page"])
            if key not in seen:
                seen.add(key)
                out.append(r)
    out.sort(key=lambda r: (r["title"], r["page"]))
    return out
