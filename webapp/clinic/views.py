from collections import Counter

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import OuterRef, Q, Subquery
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from features import DISCLAIMER, GROUPS
from rag import evidence as ev
from rag import index as rag_index
from rag import llm

from . import alerts as alert_rules
from . import care, microbiome
from . import referrals as referral_rules
from . import services as svc
from .forms import MonitoringForm, PatientForm, TreatmentForm, entry_sections
from .models import Alert, Assessment, EvidenceSummary, Patient, Report
from .presentation import assessment_comparison, clinical_snapshot, risk_history


def _patient_list(request):
    q = request.GET.get("q", "").strip()
    latest = Assessment.objects.filter(patient_id=OuterRef("pk")).order_by("-created", "-pk")
    qs = Patient.objects.annotate(
        latest_tier=Subquery(latest.values("tier")[:1]),
        latest_assessed=Subquery(latest.values("created")[:1]),
    )
    risk = request.GET.get("risk", "")
    if risk in ("High", "Moderate", "Low"):
        qs = qs.filter(latest_tier=risk)
    elif risk == "unassessed":
        qs = qs.filter(latest_tier__isnull=True)
    if q:
        filt = Q(patient_code__icontains=q)
        if q.isdigit():
            filt |= Q(data__age_years=int(q))
        if q.lower() in ("male", "female"):
            filt |= Q(data__sex=q.capitalize())
        qs = qs.filter(filt)
    page = Paginator(qs, 10).get_page(request.GET.get("page"))
    return q, page


@login_required
def dashboard(request):
    latest = Assessment.objects.filter(patient_id=OuterRef("patient_id")).order_by("-created", "-pk").values("pk")[:1]
    high = Assessment.objects.filter(pk=Subquery(latest), tier="High").select_related("patient")
    current_tiers = list(Assessment.objects.filter(pk=Subquery(latest)).values_list("tier", flat=True))
    counts = Counter(current_tiers)
    distribution = [{"tier": tier, "count": counts[tier],
                     "percent": round(counts[tier] / len(current_tiers) * 100, 1) if current_tiers else 0}
                    for tier in ("Low", "Moderate", "High")]
    return render(request, "clinic/dashboard.html", {
        "nav": "dashboard",
        "n_patients": Patient.objects.count(),
        "n_assessments": Assessment.objects.count(),
        "n_high": high.count(),
        "attention": high[:5],
        "recent": Assessment.objects.select_related("patient").order_by("-created", "-pk")[:8],
        "distribution": distribution, "distribution_count": len(current_tiers),
        "open_alerts": care.urgent_first(Alert.objects.filter(status="open").select_related("patient"))[:5],
        "n_open_alerts": Alert.objects.filter(status="open").count(),
        "overdue": care.overdue_plans()[:5],
    })


@login_required
def patients(request):
    q, page = _patient_list(request)
    return render(request, "clinic/patients.html", {
        "nav": "patients", "q": q, "page": page, "risk": request.GET.get("risk", "")})


@login_required
def patient(request, pk):
    p = get_object_or_404(Patient, pk=pk)
    section = request.GET.get("section", "overview")
    if section not in ("overview", "assessments", "care", "clinical"):
        section = "overview"
    groups = svc.grouped_data(p.data)
    last = p.assessments.order_by("-created", "-pk").first()
    history = risk_history(p)
    plan = p.monitoring if hasattr(p, "monitoring") else None
    return render(request, "clinic/patient.html", {
        "plan": plan, "monitoring_form": MonitoringForm(instance=plan), "treatment_form": TreatmentForm(),
        "treatments": p.treatments.all(), "open_alerts": care.urgent_first(p.alerts.filter(status="open")),
        "plan_overdue": bool(plan and plan.active and plan.next_due < care.today()),
        "treatment_markers": care.treatment_markers(p, history),
        "nav": "patients", "patient": p, "section": section, "groups": groups,
        "microbiome": microbiome.patient_ranges(p.data),
        "last": last, "snapshot": clinical_snapshot(p.data, last),
        "comparison": assessment_comparison(last),
        "risk_history": history,
        "history": Paginator(p.assessments.order_by("-created", "-pk"), 10).get_page(request.GET.get("page")),
        "biomarkers": next(g["items"] for g in groups if g["group"] == "Inflammatory biomarkers"),
        "red_flags": [i for g in groups if g["group"] == "Red flags" for i in g["items"]
                      if i["value"] == "Yes" and i["feature"] not in ("appendectomy_history", "tonsillectomy_history")],
        "history_items": [i for g in groups for i in g["items"]
                          if g["group"] in ("Family history", "Medication and antibiotics")
                          or i["feature"] in ("appendectomy_history", "tonsillectomy_history")],
    })


@login_required
def patient_new(request):
    form = PatientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        code = form.cleaned_data["patient_code"].strip() or f"MAN-{Patient.objects.filter(source='manual').count() + 1:05d}"
        if Patient.objects.filter(patient_code=code).exists():
            form.add_error("patient_code", "A patient with this ID already exists.")
        else:
            p = Patient.objects.create(patient_code=code, source="manual", data=form.patient_data())
            messages.success(request, f"Patient {code} saved.")
            return redirect("patient", pk=p.pk)
    return render(request, "clinic/patient_form.html", {
        "nav": "patients", "form": form, "form_sections": entry_sections(form)})


@login_required
@require_POST
def assess(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    a = care.record_assessment(patient, request.user)
    return redirect("result", pk=a.pk)


@login_required
def result(request, pk):
    a = get_object_or_404(Assessment.objects.select_related("patient"), pk=pk)
    return _assessment_page(request, a, a.reports.first())


def _assessment_page(request, a, saved_report=None):
    """Compose one printable assessment from saved findings; GET performs no research or writes."""
    factors = a.factors
    groups = svc.grouped_data(a.inputs)
    flags = [i for g in groups if g["group"] == "Red flags" for i in g["items"]
             if i["value"] == "Yes" and i["feature"] not in ("appendectomy_history", "tonsillectomy_history")]
    evidence = saved_report.evidence if saved_report else []
    if not saved_report:
        cached = {(e.feature, e.direction): e for e in EvidenceSummary.objects.filter(
            feature__in=[f["feature"] for f in factors[:svc.N_REPORT_FACTORS]])}
        evidence = [{**f, "text": cached[(f["feature"], f["direction"])].text,
                     "references": cached[(f["feature"], f["direction"])].references}
                    for f in factors[:svc.N_REPORT_FACTORS] if (f["feature"], f["direction"]) in cached]
    evidence = [e for e in evidence if e.get("text") or e.get("references")]
    evidence_by_feature = {e["feature"]: e for e in evidence}
    display_factors = [{**f, "source_count": len(evidence_by_feature.get(f["feature"], {}).get("references", [])),
                        "has_evidence": bool(evidence_by_feature.get(f["feature"], {}).get("text") or
                                             evidence_by_feature.get(f["feature"], {}).get("references"))}
                       for f in factors]
    card = svc.model_card()
    low, moderate = card["tiers"]["Low"], card["tiers"]["Moderate"]
    return render(request, "clinic/result.html", {
        "nav": "assessments", "a": a, "patient": a.patient, "r": saved_report,
        "next_step": svc.NEXT_STEPS[a.tier], "groups": groups, "assessment_red_flags": flags,
        "microbiome": microbiome.patient_ranges(a.inputs),
        "increasing": [f for f in display_factors if f["direction"] == "raises"],
        "reducing": [f for f in display_factors if f["direction"] == "lowers"],
        "snapshot": clinical_snapshot(a.inputs, finding_features={f["feature"] for f in factors}),
        "comparison": assessment_comparison(a),
        "contribution_plot": [{**f, "bar_width": min(50, f["pct"] / 2)} for f in display_factors[:6]],
        "additional_increasing": [f for f in display_factors[6:] if f["direction"] == "raises"],
        "additional_reducing": [f for f in display_factors[6:] if f["direction"] == "lowers"],
        "supporting_evidence": evidence, "research_factors": factors[:svc.N_REPORT_FACTORS],
        "risk_widths": [low * 100, (moderate - low) * 100, (1 - moderate) * 100],
        "risk_position": max(1, min(99, a.probability * 100)), "card": card,
        "since_treatment": care.since_treatment(a), "assessment_alerts": care.urgent_first(a.alerts.all()),
        "referral_review": a.referral_reviews.first(),
    })


@login_required
def assessments(request):
    q, risk = request.GET.get("q", "").strip(), request.GET.get("risk", "")
    rows = Assessment.objects.select_related("patient").order_by("-created", "-pk")
    if q:
        rows = rows.filter(patient__patient_code__icontains=q)
    if risk in ("High", "Moderate", "Low"):
        rows = rows.filter(tier=risk)
    page = Paginator(rows, 20).get_page(request.GET.get("page"))
    return render(request, "clinic/assessments.html", {"nav": "assessments", "page": page, "q": q, "risk": risk})


@login_required
@require_POST
def report_create(request, pk):
    a = get_object_or_404(Assessment, pk=pk)
    integrated = request.POST.get("return_to") == "result"
    try:
        r = (a.reports.first() if integrated else None) or svc.build_report(a)
    except (FileNotFoundError, ValueError) as e:
        if not integrated and not isinstance(e, FileNotFoundError):
            raise
        messages.error(request, "Supporting evidence is unavailable at present. Your assessment is saved and can still be printed. Try again later or contact your system administrator.")
        return redirect("result", pk=pk)
    if integrated:
        response = redirect("result", pk=a.pk)
        response["Location"] += "#supporting-evidence"
        return response
    return redirect("report", pk=r.pk)


@login_required
def report(request, pk):
    r = get_object_or_404(Report.objects.select_related("assessment__patient"), pk=pk)
    return _assessment_page(request, r.assessment, r)


@login_required
def reports(request):
    page = Paginator(Report.objects.select_related("assessment__patient"), 20).get_page(request.GET.get("page"))
    return render(request, "clinic/reports.html", {"nav": "reports", "page": page})


@login_required
def evidence(request):
    q = request.GET.get("q", "").strip()
    ctx = {"nav": "evidence", "q": q, "llm_on": llm.available(), "disclaimer": DISCLAIMER}
    if not rag_index.exists():
        ctx["index_missing"] = True
        return render(request, "clinic/evidence.html", ctx)
    idx = rag_index.load()
    ctx["papers"] = sorted(idx.docs.values(), key=lambda d: (-(d["year"] or 0), d["title"]))
    if q:
        res = ev.answer_question(q)
        ctx["answer"] = {**res, "references": ev.serialize_refs(res["references"])}
    return render(request, "clinic/evidence.html", ctx)


@login_required
def paper(request, file):
    """Serve a PDF from the research library, only if it is part of the index."""
    if not rag_index.exists() or file not in {d["file"] for d in rag_index.load().docs.values()}:
        raise Http404
    path = settings.PAPERS_DIR / file
    if not path.is_file():
        raise Http404
    return FileResponse(open(path, "rb"), content_type="application/pdf")


@login_required
def settings_page(request):
    stats = rag_index.load().stats() if rag_index.exists() else None
    return render(request, "clinic/settings.html", {
        "nav": "settings", "llm_on": llm.available(), "model": llm.MODEL, "stats": stats,
        "card": svc.model_card(), "groups": GROUPS, "real_data": microbiome.about_summary(),
        "alert_rule_table": alert_rules.RULE_TABLE, "alert_rules_version": alert_rules.RULES_VERSION,
        "referral_rule_table": referral_rules.RULE_TABLE, "referral_rules_version": referral_rules.RULES_VERSION})
