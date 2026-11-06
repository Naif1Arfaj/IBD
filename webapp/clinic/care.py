"""Care-continuity services: reassessment, treatment review, monitoring and referral reviews.

Reuses services.run_assessment unchanged. The IBD risk model was never validated for treatment response, so
nothing here may state that a medication worked; it only reports what changed between saved assessments.
"""
from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from . import alerts as alert_rules
from . import referrals as referral_rules
from . import services as svc
from .models import Alert, Assessment, MonitoringPlan, ReferralReview


def today():
    return timezone.localdate()


def end_of_day(day):
    return timezone.make_aware(datetime.combine(day, time.max))


def latest_assessment(patient):
    return patient.assessments.order_by("-created", "-pk").first()


def current_treatment(patient, on_date=None):
    """Most recently started medication that has started and not ended on `on_date`."""
    day = on_date or today()
    for treatment in patient.treatments.filter(start_date__lte=day):
        if treatment.end_date is None or treatment.end_date >= day:
            return treatment
    return None


@transaction.atomic
def record_assessment(patient, user=None):
    """Run the unchanged risk model, label initial vs reassessment, and apply monitoring rules."""
    previous = latest_assessment(patient)
    assessment = svc.run_assessment(patient, user)
    assessment.kind = "reassessment" if previous else "initial"
    assessment.treatment = current_treatment(patient)
    assessment.save(update_fields=["kind", "treatment"])
    plan = MonitoringPlan.objects.filter(patient=patient, active=True).first()
    if plan:
        raise_alerts(plan, assessment, previous)
        plan.next_due = today() + timedelta(weeks=plan.review_interval_weeks)
        plan.save(update_fields=["next_due", "updated"])
    return assessment


def raise_alerts(plan, assessment, previous):
    """Create alerts for rules that fired, keeping at most one open alert per patient and rule."""
    created = []
    for spec in alert_rules.evaluate(plan.care_status, assessment, previous):
        alert, is_new = Alert.objects.get_or_create(
            patient=plan.patient, rule_id=spec.rule_id, status="open",
            defaults={"assessment": assessment, "rules_version": alert_rules.RULES_VERSION,
                      "severity": spec.severity, "title": spec.title, "detail": spec.detail, "source": spec.source})
        if is_new:
            created.append(alert)
    return created


def urgent_first(alerts):
    """Newest first within each severity, so a short list cannot hide an urgent alert."""
    rank = Case(When(severity="urgent", then=Value(0)), default=Value(1), output_field=IntegerField())
    return alerts.order_by(rank, "-created", "-pk")


def overdue_plans():
    """Active plans past their review date. Computed on read, so no scheduler and no writes on GET."""
    return (MonitoringPlan.objects.filter(active=True, next_due__lt=today())
            .select_related("patient").order_by("next_due", "pk"))


def set_alert_status(alert, status, user, note=""):
    alert.status = status
    alert.note = note[:300]
    alert.acted_by = user
    alert.acted_at = timezone.now()
    alert.save(update_fields=["status", "note", "acted_by", "acted_at"])


def treatment_markers(patient, history):
    """Positions for medication start dates on the existing risk-history chart."""
    if not history or history["same_timestamp"]:
        return []
    start, end = history["start"], history["end"]
    elapsed = (end - start).total_seconds()
    markers = []
    for treatment in patient.treatments.all():
        moment = timezone.make_aware(datetime.combine(treatment.start_date, time.min))
        if start <= moment <= end:
            markers.append({"treatment": treatment, "left": 3 + (moment - start).total_seconds() / elapsed * 94})
    return markers


def _change_word(before, now):
    if before is None or now is None:
        return "Not comparable"
    if before == now:
        return "No change"
    return "Higher" if now > before else "Lower"


def since_treatment(assessment):
    """Measured changes since the last assessment on or before the medication start date, or None."""
    treatment = assessment.treatment
    if treatment is None:
        return None
    baseline = (Assessment.objects.filter(patient_id=assessment.patient_id, created__lte=end_of_day(treatment.start_date))
                .exclude(pk=assessment.pk).order_by("-created", "-pk").first())
    if baseline is None:
        return None

    def number(inputs, key):
        try:
            return float(inputs.get(key))
        except (TypeError, ValueError):
            return None

    rows = []
    for key in ("fecal_calprotectin_ug_g", "CRP_mg_L"):
        before, now = number(baseline.inputs, key), number(assessment.inputs, key)
        rows.append({"label": svc.label(key), "before": svc.display_value(key, baseline.inputs.get(key)),
                     "now": svc.display_value(key, assessment.inputs.get(key)), "change": _change_word(before, now)})

    def flags(inputs):
        return {label for key, label in alert_rules.RED_FLAGS.items() if alert_rules._present(inputs.get(key))}

    before_flags, now_flags = flags(baseline.inputs), flags(assessment.inputs)
    return {
        "treatment": treatment, "baseline": baseline, "rows": rows,
        "weeks": (timezone.localtime(assessment.created).date() - treatment.start_date).days // 7,
        "new_flags": sorted(now_flags - before_flags), "cleared_flags": sorted(before_flags - now_flags),
        "estimate_before": baseline.probability, "estimate_now": assessment.probability,
    }


def create_referral_review(assessment, inputs, user=None):
    return ReferralReview.objects.create(
        patient=assessment.patient, assessment=assessment, inputs=inputs,
        result=referral_rules.prioritize(inputs, assessment), rules_version=referral_rules.RULES_VERSION,
        created_by=user if user and user.is_authenticated else None)
