"""Read-only clinical presentation. No prediction or evidence generation takes place here."""
from django.db.models import Q

from features import FEATURES, GROUPS
from . import services as svc


def recorded_value(feature, data):
    value = data.get(feature)
    return "Not recorded" if value is None else svc.display_value(feature, value)


def clinical_snapshot(data, assessment=None, finding_features=()):
    measurements = [
        {"feature": f, "label": svc.label(f), "value": recorded_value(f, data),
         "finding": f in finding_features}
        for f in ("fecal_calprotectin_ug_g", "CRP_mg_L", "vitamin_D_ng_mL")
    ]
    flags = [svc.label(f) for f in GROUPS["Red flags"]
             if f not in ("appendectomy_history", "tonsillectomy_history")
             and str(data.get(f)) in ("1", "1.0", "Yes")]
    return {
        "measurements": measurements, "flags": flags, "assessment": assessment,
        "outdated": assessment is not None and data != assessment.inputs,
        "family_history": recorded_value("family_history_IBD", data),
        "antibiotics": recorded_value("antibiotic_courses_year", data),
    }


def risk_history(patient, limit=20):
    """Plot saved probabilities on a fixed scale, never infer a clinical trajectory."""
    records = list(patient.assessments.order_by("-created", "-pk")[:limit])
    if len(records) < 2:
        return None
    records.reverse()
    start, end = records[0].created, records[-1].created
    elapsed = (end - start).total_seconds()
    points = []
    for index, assessment in enumerate(records):
        fraction = ((assessment.created - start).total_seconds() / elapsed
                    if elapsed else index / (len(records) - 1))
        x = 3 + fraction * 94
        y = 5 + (1 - max(0, min(1, assessment.probability))) * 90
        points.append({"assessment": assessment, "left": x, "top": y,
                       "x": x * 6, "y": y * 1.6})
    path = " ".join(f"{'M' if i == 0 else 'L'} {p['x']:.2f},{p['y']:.2f}"
                    for i, p in enumerate(points))
    return {"points": points, "path": path, "start": start, "end": end,
            "count": len(records), "total": patient.assessments.count(),
            "same_timestamp": elapsed == 0,
            "mixed_methods": len({(a.model_name, a.threshold) for a in records}) > 1}


def assessment_comparison(assessment):
    if assessment is None:
        return None
    previous = assessment.patient.assessments.filter(
        Q(created__lt=assessment.created) |
        Q(created=assessment.created, pk__lt=assessment.pk)
    ).order_by("-created", "-pk").first()
    if previous is None:
        return None
    comparable = (previous.model_name == assessment.model_name and
                  previous.threshold == assessment.threshold)
    delta = round((assessment.probability - previous.probability) * 100, 1)
    if delta == 0:
        delta_text = "No change at displayed precision"
    else:
        delta_text = f"{abs(delta):.1f} percentage points {'higher' if delta > 0 else 'lower'}"
    changes = [
        {"label": svc.label(f), "previous": recorded_value(f, previous.inputs),
         "current": recorded_value(f, assessment.inputs)}
        for f in FEATURES if previous.inputs.get(f) != assessment.inputs.get(f)
    ]
    return {
        "previous": previous, "current": assessment, "comparable": comparable,
        "show_plot": comparable and delta != 0,
        "delta_text": delta_text if comparable else "Different assessment methods",
        "change_count": len(changes), "changes": changes,
        "previous_position": 12 + max(0, min(1, previous.probability)) * 296,
        "current_position": 12 + max(0, min(1, assessment.probability)) * 296,
    }
