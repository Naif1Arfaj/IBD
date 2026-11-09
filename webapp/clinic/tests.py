from unittest import mock

import numpy as np
import pandas as pd
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from features import FEATURES, MODEL_COLUMNS, NO_NARRATE, by_feature, encode, json_value, load_raw
from predict import predict_ibd
from rag import index as rag_index

from . import services as svc
from .forms import PatientForm
from .models import Assessment, EvidenceSummary, Patient, Report
from .templatetags.clinic_tags import readable_text


def _py(v):
    return json_value(v)


class PresentationTests(SimpleTestCase):
    def test_reference_text_repairs_encoding_without_changing_valid_units(self):
        title = "Maternal\u2013Fetal"
        self.assertEqual(readable_text(title.encode("utf-8").decode("cp1252")), title)
        self.assertEqual(readable_text("235 \u00b5g/g"), "235 \u00b5g/g")


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        raw = load_raw()
        cls.rows = {}
        for label in (1, 0):
            r = raw[raw.synthetic_IBD_outcome == label].iloc[0]
            cls.rows[label] = Patient.objects.create(
                patient_code=r.patient_id, source="synthetic", synthetic_label=label,
                data={f: _py(r[f]) for f in FEATURES})
        cls.user = get_user_model().objects.create_user("nurse", password="pw")

    def setUp(self):
        self.client.login(username="nurse", password="pw")


class AssessmentTests(Base):
    def test_matches_predict_ibd(self):
        p = self.rows[1]
        a = svc.run_assessment(p)
        ref = predict_ibd(p.data)
        self.assertAlmostEqual(a.probability, ref["probability"], places=3)
        self.assertEqual(a.prediction, ref["prediction"])
        self.assertEqual(a.tier, ref["risk_tier"])

    def test_no_narrate_variables_hidden(self):
        a = svc.run_assessment(self.rows[1])
        self.assertFalse({f["feature"] for f in a.factors} & set(NO_NARRATE))

    def test_group_shap_sums_to_feature_total(self):
        p = self.rows[0]
        a = svc.run_assessment(p)
        from predict import _load
        _, explainer = _load()
        sv = by_feature(explainer(encode(pd.DataFrame([p.data])))[0])  # pain-location columns summed per input
        expected = sum(v for f, v in zip(FEATURES, sv) if f not in NO_NARRATE)
        self.assertAlmostEqual(sum(g["shap"] for g in a.group_factors), expected, places=2)


class FormTests(Base):
    def test_round_trip_into_encode(self):
        form = PatientForm()
        data = {name: (f.initial if f.initial is not None else "") for name, f in form.fields.items()}
        data["patient_code"] = "MAN-TEST"
        form = PatientForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        X = encode(pd.DataFrame([form.patient_data()]))
        self.assertEqual(X.shape, (1, len(MODEL_COLUMNS)))

    def test_out_of_range_rejected(self):
        form = PatientForm()
        data = {name: f.initial for name, f in form.fields.items()}
        data["age_years"] = 80
        self.assertFalse(PatientForm(data).is_valid())


class PageTests(Base):
    def test_comparison_uses_preceding_assessment_for_the_same_patient(self):
        old = svc.run_assessment(self.rows[1])
        current = svc.run_assessment(self.rows[1])
        future = svc.run_assessment(self.rows[1])
        svc.run_assessment(self.rows[0])
        Assessment.objects.filter(pk__in=[old.pk, current.pk, future.pk]).update(created=old.created)
        Assessment.objects.filter(pk=old.pk).update(probability=0.2)
        Assessment.objects.filter(pk=current.pk).update(probability=0.35)
        page = self.client.get(reverse("result", args=[current.pk]))
        comparison = page.context["comparison"]
        self.assertEqual(comparison["previous"].pk, old.pk)
        self.assertEqual(comparison["delta_text"], "15.0 percentage points higher")
        self.assertTrue(comparison["show_plot"])
        self.assertEqual(comparison["change_count"], 0)
        self.assertContains(page, "not confirm clinical improvement or deterioration")

    def test_first_assessment_has_no_fabricated_comparison(self):
        a = svc.run_assessment(self.rows[1])
        page = self.client.get(reverse("result", args=[a.pk]))
        self.assertIsNone(page.context["comparison"])
        patient = self.client.get(reverse("patient", args=[a.patient_id]))
        self.assertContains(patient, "First saved assessment")

    def test_subprecision_difference_does_not_display_a_trend(self):
        old = svc.run_assessment(self.rows[1])
        current = svc.run_assessment(self.rows[1])
        Assessment.objects.filter(pk=old.pk).update(probability=0.2)
        Assessment.objects.filter(pk=current.pk).update(probability=0.20000001)
        page = self.client.get(reverse("result", args=[current.pk]))
        self.assertEqual(page.context["comparison"]["delta_text"], "No change at displayed precision")
        self.assertFalse(page.context["comparison"]["show_plot"])
        self.assertNotContains(page, 'class="comparison-plot"')

    def test_different_methods_suppress_change_calculation(self):
        old = svc.run_assessment(self.rows[1])
        Assessment.objects.filter(pk=old.pk).update(model_name="Earlier assessment method")
        current = svc.run_assessment(self.rows[1])
        page = self.client.get(reverse("result", args=[current.pk]))
        self.assertFalse(page.context["comparison"]["comparable"])
        self.assertContains(page, "Different assessment methods")
        self.assertNotContains(page, 'class="comparison-plot"')
        patient_page = self.client.get(reverse("patient", args=[current.patient_id]))
        self.assertTrue(patient_page.context["risk_history"]["mixed_methods"])
        self.assertContains(patient_page, "estimates may not be directly comparable")

    def test_snapshot_uses_saved_inputs_and_comparison_identifies_changed_values(self):
        old = svc.run_assessment(self.rows[1])
        p = self.rows[1]
        data = dict(p.data)
        data["CRP_mg_L"] = float(data["CRP_mg_L"]) + 1
        p.data = data
        p.save(update_fields=["data"])
        patient_page = self.client.get(reverse("patient", args=[p.pk]))
        self.assertTrue(patient_page.context["snapshot"]["outdated"])
        self.assertContains(patient_page, "Recorded information has changed since the latest assessment")
        current = svc.run_assessment(p)
        old_page = self.client.get(reverse("result", args=[old.pk]))
        values = {m["feature"]: m["value"] for m in old_page.context["snapshot"]["measurements"]}
        self.assertEqual(values["CRP_mg_L"], svc.display_value("CRP_mg_L", old.inputs["CRP_mg_L"]))
        page = self.client.get(reverse("result", args=[current.pk]))
        comparison = page.context["comparison"]
        self.assertEqual(comparison["change_count"], 1)
        self.assertEqual(comparison["changes"][0]["label"], svc.label("CRP_mg_L"))

    def test_finding_links_to_its_evidence_without_altering_saved_explanation(self):
        a = svc.run_assessment(self.rows[1])
        original = list(a.factors)
        f = a.factors[0]
        EvidenceSummary.objects.create(feature=f["feature"], direction=f["direction"],
            text="Supporting literature [1].", references=[{
                "file": "test-source.pdf", "page": 1, "n": 1,
                "label": "Clinical source", "quotes": ["A source passage."]}])
        empty = a.factors[1]
        EvidenceSummary.objects.create(feature=empty["feature"], direction=empty["direction"],
                                       text="", references=[])
        page = self.client.get(reverse("result", args=[a.pk]))
        self.assertContains(page, f'href="#evidence-{f["feature"]}"')
        self.assertContains(page, f'id="evidence-{f["feature"]}"')
        self.assertContains(page, f'href="#finding-{f["feature"]}"')
        self.assertContains(page, "Clinical source")
        self.assertNotContains(page, f'id="evidence-{empty["feature"]}"')
        a.refresh_from_db()
        self.assertEqual(a.factors, original)

    @mock.patch("clinic.views.rag_index.exists", return_value=False)
    def test_evidence_unavailable_has_clinical_guidance(self, _):
        page = self.client.get(reverse("evidence"))
        self.assertContains(page, "Contact your system administrator")
        self.assertNotContains(page, "manage.py")
        self.assertContains(page, "<h1>Evidence library</h1>", html=True)

    def test_patient_search_empty_preserves_recovery_action(self):
        page = self.client.get(reverse("patients"), {"q": "missing-record"})
        self.assertContains(page, "No matching patient")
        self.assertContains(page, "Clear search")
        self.assertNotContains(page, "load_patients")

    def test_report_renders_saved_findings_without_engineering_metadata(self):
        a = svc.run_assessment(self.rows[1])
        report = Report.objects.create(
            assessment=a, narrative="Saved assessment summary.", evidence=[],
            narrative_refs=[], notice="Offline mode: no Anthropic API key configured.")
        page = self.client.get(reverse("report", args=[report.pk]))
        self.assertContains(page, "Saved assessment summary.")
        self.assertContains(page, "Print / save PDF")
        self.assertContains(page, "Intended use &amp; safety")
        for internal in ("API key", "log-odds", "Evidence engine", "Team NH-74"):
            self.assertNotContains(page, internal)

    def test_login_required(self):
        self.client.logout()
        for name in ("dashboard", "patients", "assessments", "reports", "evidence", "settings"):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)

    def test_pages_render(self):
        for name in ("dashboard", "patients", "patient_new", "assessments", "reports", "settings"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.get(reverse("patient", args=[self.rows[1].pk])).status_code, 200)

    def test_assess_flow(self):
        r = self.client.post(reverse("assess", args=[self.rows[1].pk]))
        a = Assessment.objects.get()
        self.assertRedirects(r, reverse("result", args=[a.pk]))
        page = self.client.get(reverse("result", args=[a.pk]))
        self.assertContains(page, "Factors influencing this assessment")
        self.assertContains(page, "Synthetic data only")
        self.assertContains(page, "Print / save PDF")
        self.assertNotContains(page, "Generate report")
        self.assertEqual(Report.objects.count(), 0)

    def test_directory_and_patient_record_are_separate(self):
        page = self.client.get(reverse("patients"))
        self.assertContains(page, "Patient directory", html=False)
        self.assertNotContains(page, "Run assessment")
        for section in ("overview", "assessments", "clinical"):
            detail = self.client.get(reverse("patient", args=[self.rows[1].pk]), {"section": section})
            self.assertContains(detail, self.rows[1].patient_code)
            self.assertEqual(detail.context["section"], section)
        self.assertNotContains(detail, 'id="patient-search"')

    def test_latest_risk_filters_and_attention_do_not_use_old_results(self):
        old = svc.run_assessment(self.rows[1])
        Assessment.objects.filter(pk=old.pk).update(tier="High")
        latest = svc.run_assessment(self.rows[1])
        Assessment.objects.filter(pk=latest.pk).update(tier="Low")
        # Equal clock timestamps must still select the most recently saved assessment.
        Assessment.objects.filter(pk__in=[old.pk, latest.pk]).update(created=old.created)
        page = self.client.get(reverse("patients"), {"risk": "High"})
        self.assertEqual(page.context["page"].paginator.count, 0)
        overview = self.client.get(reverse("dashboard"))
        self.assertEqual(overview.context["n_high"], 0)
        history = self.client.get(reverse("assessments"), {"risk": "High"})
        self.assertEqual(history.context["page"].paginator.count, 1)

    def test_current_risk_distribution_uses_latest_assessment_per_patient(self):
        old = svc.run_assessment(self.rows[1])
        Assessment.objects.filter(pk=old.pk).update(tier="High")
        values = {f.attname: getattr(old, f.attname) for f in Assessment._meta.fields
                  if f.name not in ("id", "created", "tier")}
        Assessment.objects.bulk_create([Assessment(**values, tier="Low") for _ in range(30)])
        page = self.client.get(reverse("dashboard"))
        self.assertEqual(page.context["distribution_count"], 1)
        self.assertEqual({d["tier"]: d["count"] for d in page.context["distribution"]},
                         {"Low": 1, "Moderate": 0, "High": 0})
        self.assertContains(page, 'aria-label="Collapse navigation"')
        patient_page = self.client.get(reverse("patient", args=[old.patient_id]))
        history = patient_page.context["risk_history"]
        self.assertEqual((history["count"], history["total"]), (20, 31))
        self.assertTrue(all(p["assessment"].tier == "Low" for p in history["points"]))

    def test_patient_history_plot_uses_saved_values_and_fixed_probability_scale(self):
        old = svc.run_assessment(self.rows[1])
        current = svc.run_assessment(self.rows[1])
        Assessment.objects.filter(pk=old.pk).update(probability=0.2)
        Assessment.objects.filter(pk=current.pk).update(probability=0.8)
        page = self.client.get(reverse("patient", args=[current.patient_id]))
        points = page.context["risk_history"]["points"]
        self.assertEqual([p["assessment"].pk for p in points], [old.pk, current.pk])
        self.assertAlmostEqual(points[0]["top"], 77)
        self.assertAlmostEqual(points[1]["top"], 23)
        self.assertContains(page, "Estimated IBD risk over time")
        self.assertContains(page, "not disease progression, improvement or deterioration")

    def test_single_assessment_does_not_create_a_history_plot(self):
        a = svc.run_assessment(self.rows[1])
        page = self.client.get(reverse("patient", args=[a.patient_id]))
        self.assertIsNone(page.context["risk_history"])
        self.assertNotContains(page, 'class="history-graph"')

    def test_diverging_plot_keeps_each_finding_target_unique(self):
        a = svc.run_assessment(self.rows[1])
        page = self.client.get(reverse("result", args=[a.pk]))
        self.assertContains(page, 'class="contribution-plot"')
        self.assertEqual(len(page.context["contribution_plot"]), min(6, len(a.factors)))
        html = page.content.decode()
        for factor in a.factors:
            self.assertEqual(html.count(f'id="finding-{factor["feature"]}"'), 1)
        self.assertTrue(all(0 <= f["bar_width"] <= 50 for f in page.context["contribution_plot"]))

    def test_about_is_structured_and_main_title_has_no_icon(self):
        page = self.client.get(reverse("settings"))
        for section in ("WHAT IBD CARE DOES", "Intended clinical use", "human remains in control", "Synthetic/demo data",
                        "Validation status", "Technical transparency"):
            self.assertContains(page, section)
        self.assertContains(page, '<h1>About AIGUT</h1>', html=True)

    def test_empty_distribution_does_not_imply_any_assessments(self):
        page = self.client.get(reverse("dashboard"))
        self.assertEqual(page.context["distribution_count"], 0)
        self.assertTrue(all(d["count"] == 0 and d["percent"] == 0
                            for d in page.context["distribution"]))
        self.assertContains(page, "No patients currently have a high-risk latest assessment")

    @mock.patch("clinic.services.build_report")
    def test_result_reads_cached_evidence_without_creating_reports(self, build):
        a = svc.run_assessment(self.rows[1])
        f = a.factors[0]
        EvidenceSummary.objects.create(feature=f["feature"], direction=f["direction"],
                                       text="A saved literature summary.", references=[])
        page = self.client.get(reverse("result", args=[a.pk]))
        self.assertContains(page, "A saved literature summary.")
        self.assertEqual(Report.objects.count(), 0)
        build.assert_not_called()

    @mock.patch("clinic.services.build_report")
    def test_optional_evidence_reuses_saved_report_and_returns_to_result(self, build):
        a = svc.run_assessment(self.rows[1])
        Report.objects.create(assessment=a, narrative="Existing summary")
        response = self.client.post(reverse("report_create", args=[a.pk]), {"return_to": "result"})
        self.assertRedirects(response, reverse("result", args=[a.pk]) + "#supporting-evidence")
        self.assertEqual(a.reports.count(), 1)
        build.assert_not_called()

    @mock.patch("clinic.services.build_report", side_effect=ValueError("internal embedding download failure"))
    def test_evidence_failure_preserves_printable_assessment(self, _):
        a = svc.run_assessment(self.rows[1])
        response = self.client.post(reverse("report_create", args=[a.pk]), {"return_to": "result"}, follow=True)
        self.assertContains(response, "Your assessment is saved and can still be printed")
        self.assertContains(response, "Print / save PDF")
        self.assertNotContains(response, "embedding")

    def test_patient_form_groups_every_existing_input_once(self):
        page = self.client.get(reverse("patient_new"))
        sections = page.context["form_sections"]
        fields = [f.name for section in sections for f in section["fields"]]
        self.assertEqual(len(sections), 7)
        self.assertCountEqual(fields, FEATURES)

    def test_invalid_entry_opens_the_section_and_links_to_the_field(self):
        form = PatientForm()
        data = {name: f.initial for name, f in form.fields.items()}
        data.update(patient_code="CHECK-VALIDATION", age_years=80)
        page = self.client.post(reverse("patient_new"), data)
        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.context["form_sections"][0]["has_errors"])
        self.assertContains(page, 'href="#id_age_years"')
        self.assertNotContains(page, "Patient CHECK-VALIDATION saved")

    def test_add_patient(self):
        form = PatientForm()
        data = {name: f.initial for name, f in form.fields.items()}
        data["patient_code"] = "MAN-00001"
        r = self.client.post(reverse("patient_new"), data)
        p = Patient.objects.get(patient_code="MAN-00001")
        self.assertRedirects(r, reverse("patient", args=[p.pk]))


class OfflineReportTests(Base):
    def setUp(self):
        super().setUp()
        if not rag_index.exists():
            self.skipTest("research index not built")

    @mock.patch("rag.llm.available", return_value=False)
    def test_evidence_load_returns_to_the_printable_assessment(self, _):
        a = svc.run_assessment(self.rows[1])
        response = self.client.post(reverse("report_create", args=[a.pk]), {"return_to": "result"})
        self.assertRedirects(response, reverse("result", args=[a.pk]) + "#supporting-evidence")
        self.assertEqual(a.reports.count(), 1)
        page = self.client.get(reverse("result", args=[a.pk]))
        self.assertContains(page, "Supporting evidence")
        self.assertContains(page, "Print / save PDF")
        self.assertNotContains(page, "Generate report")

    @mock.patch("rag.llm.available", return_value=False)
    def test_offline_report_has_citations(self, _):
        a = svc.run_assessment(self.rows[1])
        r = self.client.post(reverse("report_create", args=[a.pk]))
        rep = a.reports.get()
        self.assertRedirects(r, reverse("report", args=[rep.pk]))
        self.assertFalse(rep.llm_used)
        self.assertTrue(rep.narrative)
        self.assertTrue(all(e["references"] for e in rep.evidence))
        page = self.client.get(reverse("report", args=[rep.pk]))
        self.assertContains(page, "Supporting evidence")
        self.assertNotContains(page, "appendectomy_history")

    @mock.patch("rag.llm.available", return_value=False)
    def test_evidence_page_offline(self, _):
        page = self.client.get(reverse("evidence"), {"q": "antibiotic exposure risk of IBD"})
        self.assertContains(page, "antibiotic", status_code=200)
