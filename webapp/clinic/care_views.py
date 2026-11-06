"""Views for reassessment, monitoring, alerts and referral reviews."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from features import DISCLAIMER

from . import care
from .forms import (MonitoringForm, PatientEditForm, ReferralDecisionForm, ReferralForm, TreatmentForm,
                    entry_sections)
from .models import Alert, Assessment, MonitoringPlan, Patient, ReferralReview


def _first_error(form):
    for field, errors in form.errors.items():
        label = form.fields[field].label if field in form.fields else ""
        return f"{label}: {errors[0]}" if label else errors[0]
    return "Check the values and try again."


@login_required
def patient_edit(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    form = PatientEditForm(request.POST or None, patient=patient)
    if request.method == "POST" and form.is_valid():
        data = form.patient_data()
        if data != patient.data:
            patient.data = data
            patient.synthetic_label = None  # the dataset label no longer describes the changed values
            patient.save(update_fields=["data", "synthetic_label"])
        if "reassess" in request.POST:
            assessment = care.record_assessment(patient, request.user)
            return redirect("result", pk=assessment.pk)
        messages.success(request, "Values saved. Run a new assessment to use them.")
        return redirect("patient", pk=patient.pk)
    return render(request, "clinic/patient_form.html", {
        "nav": "patients", "form": form, "form_sections": entry_sections(form), "patient": patient, "is_edit": True})


@login_required
@require_POST
def treatment_add(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    form = TreatmentForm(request.POST)
    if form.is_valid():
        treatment = form.save(commit=False)
        treatment.patient = patient
        treatment.recorded_by = request.user
        treatment.save()
        messages.success(request, f"{treatment.medication} recorded. Reassess when the review is due.")
    else:
        messages.error(request, _first_error(form))
    return redirect("patient", pk=patient.pk)


@login_required
@require_POST
def monitoring_update(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    plan = MonitoringPlan.objects.filter(patient=patient).first()
    # Read this first: validating the form writes the new values onto the same plan object.
    old_interval = plan.review_interval_weeks if plan else None
    form = MonitoringForm(request.POST, instance=plan)
    if form.is_valid():
        saved = form.save(commit=False)
        saved.patient = patient
        if plan is None:
            saved.started_by = request.user
        if old_interval != saved.review_interval_weeks:
            saved.next_due = care.today() + timedelta(weeks=saved.review_interval_weeks)
        saved.save()
        messages.success(request, "Monitoring plan saved.")
    else:
        messages.error(request, _first_error(form))
    return redirect("patient", pk=patient.pk)


@login_required
def alerts(request):
    status = request.GET.get("status", "open")
    rows = Alert.objects.select_related("patient", "assessment", "acted_by")
    if status in ("open", "acknowledged", "resolved"):
        rows = rows.filter(status=status)
        if status == "open":
            rows = care.urgent_first(rows)
    else:
        status = "all"
    return render(request, "clinic/alerts.html", {
        "nav": "alerts", "status": status, "page": Paginator(rows, 20).get_page(request.GET.get("page")),
        "status_tabs": [("open", "Open"), ("acknowledged", "Acknowledged"), ("resolved", "Resolved"), ("all", "All")],
        "overdue": care.overdue_plans()[:20], "disclaimer": DISCLAIMER})


@login_required
@require_POST
def alert_action(request, pk):
    alert = get_object_or_404(Alert, pk=pk)
    status = request.POST.get("status")
    if status in ("acknowledged", "resolved"):
        care.set_alert_status(alert, status, request.user, request.POST.get("note", "").strip())
        messages.success(request, f"Alert {status}.")
    return redirect("alerts")


@login_required
def referral_new(request, pk):
    assessment = get_object_or_404(Assessment.objects.select_related("patient"), pk=pk)
    form = ReferralForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        review = care.create_referral_review(assessment, form.cleaned_data, request.user)
        return redirect("referral", pk=review.pk)
    return render(request, "clinic/referral_form.html", {
        "nav": "assessments", "a": assessment, "patient": assessment.patient, "form": form})


@login_required
def referral(request, pk):
    review = get_object_or_404(ReferralReview.objects.select_related("patient", "assessment", "decided_by"), pk=pk)
    return render(request, "clinic/referral.html", {
        "nav": "assessments", "review": review, "patient": review.patient, "a": review.assessment,
        "form": ReferralDecisionForm(), "disclaimer": DISCLAIMER})


@login_required
@require_POST
def referral_decision(request, pk):
    review = get_object_or_404(ReferralReview, pk=pk)
    form = ReferralDecisionForm(request.POST)
    if form.is_valid():
        review.decision = form.cleaned_data["decision"]
        review.decision_reason = form.cleaned_data["decision_reason"]
        review.decided_by = request.user
        review.save(update_fields=["decision", "decision_reason", "decided_by"])
        messages.success(request, "Decision saved.")
    else:
        messages.error(request, _first_error(form))
    return redirect("referral", pk=review.pk)
