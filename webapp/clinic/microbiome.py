"""Real-cohort microbiome ranges for display. Read-only: nothing here feeds the risk model."""
import json
from functools import lru_cache
from math import log10

from django.conf import settings

from features import GROUPS

from . import services as svc

REFERENCE_PATH = settings.IBD_ROOT / "artifacts" / "microbiome_reference.json"
# A few people with almost no Bacteroidetes have very large ratios, so a linear axis would hide everyone else.
LOG_SCALE = {"Firmicutes_Bacteroidetes_ratio"}
ROW_NOTES = {"butyrate_producer_abundance_pct": "The genus list behind this total is our own working definition."}


@lru_cache(maxsize=1)
def reference():
    try:
        return json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value, unit=""):
    return f"{value:.3g}{'%' if unit == '%' else ''}"


def _axis(feature, points, value):
    high = max(points + ([value] if value is not None else []))
    if feature in LOG_SCALE:
        low = min(p for p in points if p > 0)
        if value is not None and value > 0:
            low = min(low, value)
        return low / 1.5, high * 1.5
    return 0.0, (high * 1.05) or 1.0


def _position(value, axis, is_log):
    low, high = axis
    if is_log:
        share = (log10(max(value, low)) - log10(low)) / (log10(high) - log10(low))
    else:
        share = (value - low) / (high - low)
    return round(100 * min(1.0, max(0.0, share)), 2)


def _outside_note(value, low, high):
    if value is None:
        return ""
    if value < low:
        return "Below the 5th–95th percentile range of all three groups."
    if value > high:
        return "Above the 5th–95th percentile range of all three groups."
    return ""


def patient_ranges(data):
    """One row per microbiome input, placing the patient's value against each real group."""
    ref = reference()
    if ref is None:
        return None
    rows = []
    for feature in GROUPS["Microbiome diversity"]:
        entry = ref["features"][feature]
        value = _number(data.get(feature))
        spread = [g[p] for g in entry["groups"].values() for p in ("p5", "p95")]
        axis = _axis(feature, spread, value)
        is_log = feature in LOG_SCALE
        place = lambda point: _position(point, axis, is_log)  # noqa: E731
        groups = []
        for key, g in entry["groups"].items():
            label = ref["group_labels"][key]
            stat = f"{_text(g['p50'], entry['unit'])} ({_text(g['p5'], entry['unit'])}–{_text(g['p95'], entry['unit'])})"
            groups.append({
                "label": label, "people": g["people"], "stat": stat,
                "left": place(g["p5"]), "width": round(place(g["p95"]) - place(g["p5"]), 2),
                "box_left": place(g["p25"]), "box_width": round(place(g["p75"]) - place(g["p25"]), 2),
                "median": place(g["p50"]),
            })
        rows.append({
            "feature": feature, "label": svc.label(feature), "groups": groups,
            "value": None if value is None else _text(value, entry["unit"]),
            "marker": None if value is None else place(value),
            "outside": _outside_note(value, min(spread), max(spread)), "note": ROW_NOTES.get(feature, ""),
            "axis_low": _text(axis[0], entry["unit"]), "axis_high": _text(axis[1], entry["unit"]), "is_log": is_log,
        })
    return {"rows": rows, "age_low": int(ref["cohort"]["age_range"][0]), "age_high": int(ref["cohort"]["age_range"][1])}


def about_summary():
    """The real-data findings shown on the About page, all read from the built reference file."""
    ref = reference()
    if ref is None:
        return None
    signal, cohort = ref["signal"], ref["cohort"]
    return {
        "source": ref["source"], "samples": cohort["samples"], "people": sum(cohort["people"].values()),
        "non_ibd_people": cohort["people"]["nonIBD"], "crohns_people": cohort["people"]["CD"],
        "colitis_people": cohort["people"]["UC"],
        "age_low": int(cohort["age_range"][0]), "age_high": int(cohort["age_range"][1]),
        "butyrate_genera": ", ".join(ref["butyrate_genera"]),
        "signal": [
            ("IBD vs non-IBD from the 7 inputs (logistic regression)", f"AUC {signal['logistic_auc']:.2f}"),
            ("IBD vs non-IBD from the 7 inputs (random forest)", f"AUC {signal['forest_auc']:.2f}"),
            ("Active disease at the next visit, from a remission-visit sample",
             f"AUC {signal['next_visit_auc']:.2f} ({signal['next_visit_events']} events)"),
        ],
        "careless_auc": f"{signal['careless_species_auc']:.3f}", "grouped_auc": f"{signal['grouped_species_auc']:.2f}",
        "synthetic": [{"label": svc.label(f), "median": _text(e["synthetic_median"], e["unit"]),
                       "outside": f"{e['synthetic_outside_pct']:.0f}%"} for f, e in ref["features"].items()],
        "dysbiosis": [{"label": ref["group_labels"][k], **d} for k, d in ref["dysbiosis"]["groups"].items()],
        "sources": ref["sources"],
    }
