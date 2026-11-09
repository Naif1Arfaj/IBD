"""Signs and symptoms, the new blood tests, the AIGUT name, and compatibility with older records."""
import json
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
from django.core.management import call_command
from django.test import SimpleTestCase
from django.urls import reverse

from features import (BLANK_MEANS_NONE, FEATURES, GROUPS, MODEL_COLUMNS, OPTIONAL, OPTIONAL_BINARY_COLS, SYMPTOMS,
                      by_feature, encode, load_raw)
from predict import predict_ibd

from . import services as svc
from .forms import PatientForm
from .models import Patient
from .tests import Base

ORIGINAL_RED_FLAGS = ["perianal_fistula_history", "recurrent_aphthous_ulcers", "erythema_nodosum_history",
                      "pyoderma_gangrenosum_history", "hidradenitis_suppurativa_history", "PSC_or_elevated_LFTs",
                      "unprovoked_VTE_history", "appendectomy_history", "tonsillectomy_history"]
NEW_BLOOD_TESTS = ["anemia_status", "hemoglobin_g_dL", "WBC_10e9_L", "platelet_count_10e9_L", "MCV_fL", "ESR_mm_h"]


class InputDefinitionTests(SimpleTestCase):
    def test_section_order(self):
        self.assertEqual(list(GROUPS), [
            "Demographic data", "Signs and symptoms", "Family history", "Diet", "Lifestyle",
            "Medication and antibiotics", "Birth mode and early life", "Microbiome diversity",
            "Inflammatory biomarkers", "Metabolism related biomarkers", "Red flags"])

    def test_symptoms_run_from_diarrhoea_to_reduced_energy(self):
        self.assertEqual(SYMPTOMS[0], "diarrhea")
        self.assertEqual(SYMPTOMS[-1], "reduced_energy_levels")
        self.assertEqual(len(SYMPTOMS), 31)

    def test_inflammatory_biomarkers_keep_the_original_three_then_the_blood_tests(self):
        self.assertEqual(GROUPS["Inflammatory biomarkers"],
                         ["fecal_calprotectin_ug_g", "CRP_mg_L", "vitamin_D_ng_mL", *NEW_BLOOD_TESTS])

    def test_red_flags_unchanged_and_unused_columns_left_out(self):
        self.assertEqual(GROUPS["Red flags"], ORIGINAL_RED_FLAGS)
        for column in ("fecal_occult_blood_test_positive", "perianal_symptoms_current", "oral_ulcers_current",
                       "joint_pain", "skin_manifestations_current", "eye_inflammation_symptoms"):
            self.assertNotIn(column, FEATURES)

    def test_ninety_eight_inputs_and_pain_location_one_hot(self):
        self.assertEqual(len(FEATURES), 98)
        self.assertEqual(len(MODEL_COLUMNS), 103)
        self.assertEqual(by_feature(np.ones(len(MODEL_COLUMNS)))[FEATURES.index("abdominal_pain_location")], 6)

    def test_dataset_blanks_mean_none_where_documented(self):
        raw = load_raw()
        no_pain = raw.abdominal_pain == 0
        self.assertTrue(raw.abdominal_pain_location[no_pain].isna().all())
        X = encode(raw)
        location = [c for c in MODEL_COLUMNS if c.startswith("abdominal_pain_location=")]
        self.assertTrue((X.loc[no_pain, location].sum(axis=1) == 0).all())
        self.assertFalse(X[["symptom_frequency", "symptom_duration_weeks"]].isna().any().any())
        self.assertIn("abdominal_pain_location", BLANK_MEANS_NONE)

    def test_original_inputs_still_required(self):
        with self.assertRaises(ValueError):
            encode(pd.DataFrame([{"diarrhea": 1}]))


class ModelTests(SimpleTestCase):
    def test_record_without_any_new_input_still_predicts(self):
        patient = json.loads((Path(__file__).resolve().parents[2] / "example_patient.json").read_text())
        self.assertFalse(set(OPTIONAL) & set(patient))
        result = predict_ibd(patient)
        self.assertTrue(0 <= result["probability"] <= 1)

    def test_blank_new_inputs_are_imputed_not_rejected(self):
        raw = load_raw()
        row = {f: raw.iloc[0][f] for f in FEATURES}
        blank = {**row, **{f: None for f in OPTIONAL}}
        self.assertTrue(0 <= predict_ibd(blank)["probability"] <= 1)

    def test_bleeding_raises_the_estimate(self):
        raw = load_raw()
        row = {f: raw.iloc[0][f] for f in FEATURES}
        base = predict_ibd({**row, "blood_in_stool": 0, "visible_rectal_bleeding": 0})["probability"]
        bleeding = predict_ibd({**row, "blood_in_stool": 1, "visible_rectal_bleeding": 1})["probability"]
        self.assertGreaterEqual(bleeding, base)


class PatientRecordTests(Base):
    def test_loaded_records_store_blanks_as_none(self):
        call_command("load_patients", stdout=StringIO())
        raw = load_raw()
        code = raw.loc[raw.ESR_mm_h.isna(), "patient_id"].iloc[0]
        data = Patient.objects.get(patient_code=code).data
        self.assertIsNone(data["ESR_mm_h"])
        self.assertTrue(set(OPTIONAL) <= set(data))

    def test_older_records_gain_symptoms_without_overwriting(self):
        call_command("load_patients", stdout=StringIO())
        p = Patient.objects.filter(source="synthetic").exclude(pk__in=[r.pk for r in self.rows.values()]).first()
        kept = {f: v for f, v in p.data.items() if f not in OPTIONAL}
        p.data = {**kept, "diarrhea": 1}
        p.save(update_fields=["data"])
        call_command("load_patients", stdout=StringIO())
        p.refresh_from_db()
        self.assertEqual(p.data["diarrhea"], 1)
        self.assertTrue(set(OPTIONAL) <= set(p.data))

    def test_older_record_without_symptoms_assesses(self):
        p = self.rows[1]
        p.data = {f: v for f, v in p.data.items() if f not in OPTIONAL}
        p.save(update_fields=["data"])
        assessment = svc.run_assessment(p, self.user)
        self.assertTrue(0 <= assessment.probability <= 1)
        page = self.client.get(reverse("result", args=[assessment.pk]))
        self.assertContains(page, "not recorded, so the estimate used a typical value")

    def test_patient_page_shows_signs_and_symptoms_second(self):
        page = self.client.get(reverse("patient", args=[self.rows[1].pk]) + "?section=clinical").content.decode()
        positions = [page.index(name) for name in ("Patient profile", "Signs and symptoms", "Family history")]
        self.assertEqual(positions, sorted(positions))
        for label in ("Diarrhoea", "Reduced energy levels", "Anaemia", "Haemoglobin level", "ESR (erythrocyte"):
            self.assertIn(label, page)

    def test_form_has_signs_and_symptoms_second_and_saves_new_values(self):
        page = self.client.get(reverse("patient_new"))
        self.assertEqual([s["label"] for s in page.context["form_sections"]][:3],
                         ["Patient profile", "Signs and symptoms", "Clinical history"])
        form = PatientForm()
        data = {name: (f.initial if f.initial is not None else "") for name, f in form.fields.items()}
        data.update(patient_code="SYMPTOM-TEST", blood_in_stool="Yes", hemoglobin_g_dL="10.5",
                    abdominal_pain_location="Right lower quadrant", symptom_frequency="Persistent")
        form = PatientForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.patient_data()
        self.assertEqual(saved["blood_in_stool"], 1)
        self.assertEqual(saved["hemoglobin_g_dL"], 10.5)
        self.assertEqual(saved["abdominal_pain_location"], "Right lower quadrant")
        self.assertIsNone(saved["ESR_mm_h"])
        self.assertIsNone(saved["nausea"])

    def test_new_binary_values_display(self):
        self.assertEqual(svc.display_value("fever", None), "Not recorded")
        self.assertEqual(svc.display_value("fever", 1), "Yes")
        self.assertEqual(svc.display_value("anemia_status", 0), "No")
        self.assertIn(OPTIONAL_BINARY_COLS[0], FEATURES)

    def test_new_name_on_pages(self):
        self.assertContains(self.client.get(reverse("dashboard")), "| AIGUT</title>")
        self.client.logout()
        login = self.client.get(reverse("login"))
        self.assertContains(login, "AIGUT")
        self.assertNotContains(login, "IBD Care")
