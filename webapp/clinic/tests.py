from unittest import mock

import numpy as np
import pandas as pd
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from features import FEATURES, NO_NARRATE, encode, load_raw
from predict import predict_ibd
from rag import index as rag_index

from . import services as svc
from .forms import PatientForm
from .models import Assessment, Patient


def _py(v):
    return v.item() if hasattr(v, "item") else v


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
        sv = np.asarray(explainer(encode(pd.DataFrame([p.data])))[0])
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
        self.assertEqual(X.shape, (1, 61))

    def test_out_of_range_rejected(self):
        form = PatientForm()
        data = {name: f.initial for name, f in form.fields.items()}
        data["age_years"] = 80
        self.assertFalse(PatientForm(data).is_valid())


class PageTests(Base):
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
        self.assertContains(page, "Key Contributing Factors")
        self.assertContains(page, "Synthetic data only")

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
    def test_offline_report_has_citations(self, _):
        a = svc.run_assessment(self.rows[1])
        r = self.client.post(reverse("report_create", args=[a.pk]))
        rep = a.reports.get()
        self.assertRedirects(r, reverse("report", args=[rep.pk]))
        self.assertFalse(rep.llm_used)
        self.assertTrue(rep.narrative)
        self.assertTrue(all(e["references"] for e in rep.evidence))
        page = self.client.get(reverse("report", args=[rep.pk]))
        self.assertContains(page, "Research evidence for the top factors")
        self.assertNotContains(page, "appendectomy_history")

    @mock.patch("rag.llm.available", return_value=False)
    def test_evidence_page_offline(self, _):
        page = self.client.get(reverse("evidence"), {"q": "antibiotic exposure risk of IBD"})
        self.assertContains(page, "antibiotic", status_code=200)
