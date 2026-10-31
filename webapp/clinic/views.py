from collections import Counter

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from features import DISCLAIMER, GROUPS
from rag import evidence as ev
from rag import index as rag_index
from rag import llm

from . import services as svc
from .forms import PatientForm
from .models import Assessment, Patient, Report

MICROBES = ["Faecalibacterium_abundance_pct", "Roseburia_abundance_pct", "Bacteroides_abundance_pct",
            "Proteobacteria_abundance_pct"]
LIFESTYLE = {"family_history_IBD": "family", "antibiotic_courses_year": "pill", "ultra_processed_food_times_week": "utensils",
             "fiber_g_day": "leaf", "fast_food_times_week": "utensils", "smoking": "alert",
             "physical_activity_min_week": "activity", "sedentary_hours_day": "clipboard", "sleep_hours": "heart",
             "stress_level": "brain"}


def _patient_list(request):
    q = request.GET.get("q", "").strip()
    qs = Patient.objects.all()
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
    tiers = Counter(Assessment.objects.values_list("tier", flat=True))
    return render(request, "clinic/dashboard.html", {
        "nav": "dashboard",
        "n_patients": Patient.objects.count(),
        "n_manual": Patient.objects.filter(source="manual").count(),
        "n_assessments": Assessment.objects.count(),
        "n_reports": Report.objects.count(),
        "tiers": [(t, tiers.get(t, 0)) for t in ("High", "Moderate", "Low")],
        "recent": Assessment.objects.select_related("patient")[:8],
        "card": svc.model_card(),
        "llm_on": llm.available(),
    })


@login_required
def patients(request, pk=None):
    q, page = _patient_list(request)
    patient = get_object_or_404(Patient, pk=pk) if pk else (page.object_list[0] if page.object_list else None)
    ctx = {"nav": "patients", "q": q, "page": page, "patient": patient}
    if patient:
        d = patient.data
        stats = svc.dataset_stats()
        shannon = float(d["alpha_diversity_Shannon"])
        ctx.update({
            "shannon": shannon,
            "shannon_level": {"low": "Lower", "typical": "Typical", "high": "Higher"}[svc.level("alpha_diversity_Shannon", shannon)],
            "shannon_pct": round(100 * shannon / stats["alpha_diversity_Shannon"]["max"]),
            "microbes": [{"label": svc.label(f), "value": d[f],
                          "pct": round(100 * float(d[f]) / stats[f]["max"]), "level": svc.level(f, d[f])}
                         for f in MICROBES],
            "fb_ratio": d["Firmicutes_Bacteroidetes_ratio"],
            "biomarkers": [{"label": svc.label(f), "value": svc.display_value(f, d[f]), "level": svc.level(f, d[f])}
                           for f in ("fecal_calprotectin_ug_g", "CRP_mg_L", "vitamin_D_ng_mL")],
            "lifestyle": [{"feature": f, "label": svc.label(f), "value": svc.display_value(f, d[f]), "icon": ic}
                          for f, ic in LIFESTYLE.items()],
            "groups": svc.grouped_data(d),
            "last": patient.assessments.first(),
        })
    return render(request, "clinic/patients.html", ctx)


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
    return render(request, "clinic/patient_form.html", {"nav": "patients", "form": form})


@login_required
@require_POST
def assess(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    a = svc.run_assessment(patient, request.user)
    return redirect("result", pk=a.pk)


@login_required
def result(request, pk):
    a = get_object_or_404(Assessment.objects.select_related("patient"), pk=pk)
    d = a.inputs
    summary = [
        ("Demographics", f"Age {d['age_years']} · {d['sex']} · BMI {d['BMI_kg_m2']}", "user"),
        ("Gut Microbiome", f"Diversity {d['alpha_diversity_Shannon']} · Proteobacteria {d['Proteobacteria_abundance_pct']}%", "microbe"),
        ("Clinical & Lifestyle", f"Family history: {d['family_history_IBD']} · Antibiotics {d['antibiotic_courses_year']}/yr", "clipboard"),
        ("Biomarkers", f"Fecal calprotectin {d['fecal_calprotectin_ug_g']} µg/g · CRP {d['CRP_mg_L']} mg/L", "flask"),
    ]
    return render(request, "clinic/result.html", {
        "nav": "assessments", "a": a, "patient": a.patient, "summary": summary,
        "next_step": svc.NEXT_STEPS[a.tier], "workflow": svc.WORKFLOW, "disclaimer": DISCLAIMER,
        "ring": round(a.probability * 100), "reports": a.reports.all()})


@login_required
def assessments(request):
    page = Paginator(Assessment.objects.select_related("patient"), 20).get_page(request.GET.get("page"))
    return render(request, "clinic/assessments.html", {"nav": "assessments", "page": page})


@login_required
@require_POST
def report_create(request, pk):
    a = get_object_or_404(Assessment, pk=pk)
    try:
        r = svc.build_report(a)
    except FileNotFoundError as e:  # research index not built
        messages.error(request, str(e))
        return redirect("result", pk=pk)
    return redirect("report", pk=r.pk)


@login_required
def report(request, pk):
    r = get_object_or_404(Report.objects.select_related("assessment__patient"), pk=pk)
    a = r.assessment
    return render(request, "clinic/report.html", {
        "nav": "reports", "r": r, "a": a, "patient": a.patient, "groups": svc.grouped_data(a.inputs),
        "card": svc.model_card(), "next_step": svc.NEXT_STEPS[a.tier], "disclaimer": DISCLAIMER,
        "bibliography": svc.bibliography(r), "ring": round(a.probability * 100)})


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
        "card": svc.model_card(), "groups": GROUPS})
