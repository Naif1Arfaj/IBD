"""Create three synthetic demonstration patients with history. Safe to run repeatedly."""
from datetime import timedelta

import pandas as pd
from django.core.management.base import BaseCommand
from django.utils import timezone

from features import FEATURES, encode, load_raw
from predict import _load as load_model

from clinic import care
from clinic.models import Assessment, MonitoringPlan, Patient, TreatmentEvent


def _py(value):
    return value.item() if hasattr(value, "item") else value


def _backdate(assessment, weeks):
    Assessment.objects.filter(pk=assessment.pk).update(created=timezone.now() - timedelta(weeks=weeks))


class Command(BaseCommand):
    help = "Seed demo scenarios: an at-risk patient progressing, a treated patient, and a referral case."

    def handle(self, *args, **options):
        codes = ["DEMO-ATRISK-01", "DEMO-TREATED-01", "DEMO-REFERRAL-01"]
        if Patient.objects.filter(patient_code__in=codes).count() == len(codes):
            self.stdout.write("Demo scenarios already present.")
            return
        raw = load_raw()
        bundle, _ = load_model()
        probability = pd.Series(bundle["model"].predict_proba(encode(raw))[:, 1], index=raw.index)

        def row(mask):
            matches = raw[mask].sort_values("patient_id")
            if matches.empty:
                raise ValueError("No synthetic row matches this demo scenario.")
            return {f: _py(matches.iloc[0][f]) for f in FEATURES}

        def patient(code, data):
            # The values are altered from the dataset row, so no dataset label applies.
            return Patient.objects.get_or_create(patient_code=code, defaults={"source": "synthetic", "data": data})

        low = (probability < 0.05) & (raw.fecal_calprotectin_ug_g < 100) & (raw.CRP_mg_L < 5)

        p, created = patient("DEMO-ATRISK-01", row(low & (raw.perianal_fistula_history == 0)))
        if created:
            MonitoringPlan.objects.create(patient=p, care_status="at_risk", review_interval_weeks=12,
                                          next_due=care.today())
            _backdate(care.record_assessment(p), 12)
            p.data = {**p.data, "fecal_calprotectin_ug_g": 320, "CRP_mg_L": 8.5, "fiber_g_day": 8,
                      "antibiotic_courses_year": 5, "ultra_processed_food_times_week": 14,
                      "alpha_diversity_Shannon": 1.8, "Proteobacteria_abundance_pct": 14,
                      "fecal_butyrate_umol_g": 15, "perianal_fistula_history": 1}
            p.save(update_fields=["data"])
            care.record_assessment(p)

        high = (probability > 0.6) & (raw.fecal_calprotectin_ug_g > 200) & (raw.CRP_mg_L > 5)
        p, created = patient("DEMO-TREATED-01", row(high))
        if created:
            MonitoringPlan.objects.create(patient=p, care_status="diagnosed", review_interval_weeks=8,
                                          next_due=care.today())
            _backdate(care.record_assessment(p), 10)
            TreatmentEvent.objects.create(patient=p, medication="Mesalazine (demo entry)",
                                          start_date=care.today() - timedelta(weeks=8),
                                          note="Synthetic demonstration record.")
            p.data = {**p.data, "fecal_calprotectin_ug_g": 90, "CRP_mg_L": 2.1}
            p.save(update_fields=["data"])
            care.record_assessment(p)
            # Show the overdue list without inventing a clinical event.
            MonitoringPlan.objects.filter(patient=p).update(next_due=care.today() - timedelta(days=7))

        p, created = patient("DEMO-REFERRAL-01", row(low & (raw.NSAID_use_times_month > 0)))
        if created:
            care.create_referral_review(care.record_assessment(p), {
                "diarrhoea_weeks": 8.0, "bloody_stools_per_day": 0, "rectal_bleeding": "no", "abdominal_pain": "yes",
                "nocturnal_symptoms": "no", "weight_loss": "no", "abdominal_or_rectal_mass": "no",
                "recent_gastroenteritis_or_travel": "no", "temperature_c": 36.8, "pulse_bpm": 76,
                "haemoglobin_g_dl": 11.9, "iron_deficiency": "unknown", "stool_infection_test": "negative",
                "celiac_serology": "positive"})
        self.stdout.write(self.style.SUCCESS("Demo scenarios ready."))
