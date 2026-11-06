from datetime import timedelta
from io import StringIO
from types import SimpleNamespace as NS

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from features import FEATURES, NO_NARRATE, load_raw
from predict import predict_ibd

from . import alerts as rules
from . import care, referrals
from .forms import PatientEditForm, PatientForm
from .models import Alert, Assessment, MonitoringPlan, Patient, ReferralReview, TreatmentEvent


def _py(value):
    return value.item() if hasattr(value, "item") else value


def A(probability=0.1, tier="Low", **inputs):
    return NS(probability=probability, tier=tier, inputs=inputs)


def ids(specs):
    return {s.rule_id for s in specs}


class AlertRuleTests(SimpleTestCase):
    def test_first_assessment_and_no_change_are_silent(self):
        self.assertEqual(rules.evaluate("at_risk", A(), None), [])
        self.assertEqual(rules.evaluate("at_risk", A(), A()), [])

    def test_tier_only_alerts_when_rising(self):
        self.assertIn("tier_up", ids(rules.evaluate("at_risk", A(.3, "Moderate"), A(.25, "Low"))))
        self.assertNotIn("tier_up", ids(rules.evaluate("at_risk", A(.1, "Low"), A(.3, "Moderate"))))

    def test_probability_boundary(self):
        self.assertIn("probability_rise", ids(rules.evaluate("at_risk", A(.30), A(.15))))
        self.assertNotIn("probability_rise", ids(rules.evaluate("at_risk", A(.29), A(.15))))

    def test_calprotectin_must_cross_the_cutoff(self):
        check = lambda now, was: ids(rules.evaluate("at_risk", A(fecal_calprotectin_ug_g=now), A(fecal_calprotectin_ug_g=was)))
        self.assertIn("calprotectin_cross", check(151, 150))
        self.assertNotIn("calprotectin_cross", check(150, 100))
        self.assertNotIn("calprotectin_cross", check(300, 200))

    def test_crp_boundary_and_missing_value(self):
        check = lambda now, was: ids(rules.evaluate("at_risk", A(CRP_mg_L=now), A(CRP_mg_L=was)))
        self.assertIn("crp_cross", check(5.1, 4))
        self.assertNotIn("crp_cross", check(5, 4))
        self.assertNotIn("crp_cross", check(None, 4))

    def test_flare_wording_is_only_for_diagnosed_patients(self):
        at_risk = rules.evaluate("at_risk", A(.9, "High"), A(.1, "Low"))
        diagnosed = rules.evaluate("diagnosed", A(.9, "High"), A(.1, "Low"))
        self.assertTrue(all("flare" not in s.title.lower() for s in at_risk))
        self.assertTrue(all("Possible flare" in s.title for s in diagnosed))

    def test_never_narrated_variables_cannot_alert(self):
        self.assertFalse(set(rules.RED_FLAGS) & set(NO_NARRATE))
        self.assertEqual(rules.evaluate("at_risk", A(appendectomy_history=1), A(appendectomy_history=0)), [])


class ReferralRuleTests(SimpleTestCase):
    base = dict(age_years=22, fecal_calprotectin_ug_g=60, CRP_mg_L=1, NSAID_use_times_month=0, perianal_fistula_history=0)
    clear = dict(rectal_bleeding="no", weight_loss="no", nocturnal_symptoms="no", iron_deficiency="no",
                 abdominal_or_rectal_mass="no", abdominal_pain="yes")

    def model(self, tier="Low", **kw):
        return NS(tier=tier, inputs={**self.base, **kw})

    def test_unknown_inputs_are_safe_and_listed(self):
        result = referrals.prioritize({}, self.model())
        self.assertEqual(result["priority"], "routine")
        self.assertEqual(result["consider"], [])
        self.assertEqual(len(result["not_recorded"]), 7)

    def test_emergency_wins_and_needs_systemic_upset(self):
        result = referrals.prioritize(dict(bloody_stools_per_day=6, pulse_bpm=95), self.model("High", perianal_fistula_history=1))
        self.assertEqual(result["priority"], "emergency")
        self.assertEqual(result["reasons"][0]["rule_id"], "E1")
        self.assertNotEqual(referrals.prioritize(dict(bloody_stools_per_day=6, pulse_bpm=90), self.model())["priority"], "emergency")
        self.assertNotEqual(referrals.prioritize(dict(bloody_stools_per_day=5, pulse_bpm=95), self.model())["priority"], "emergency")

    def test_calprotectin_rules_need_symptoms(self):
        self.assertEqual(referrals.prioritize({}, self.model(fecal_calprotectin_ug_g=500))["reasons"], [])
        over = referrals.prioritize(dict(abdominal_pain="yes"), self.model(fecal_calprotectin_ug_g=251))
        self.assertEqual(over["priority"], "urgent")

    def test_ibs_needs_every_alarm_feature_recorded_absent(self):
        names = lambda r: {c["condition"] for c in r["consider"]}
        self.assertIn("Irritable bowel syndrome", names(referrals.prioritize(self.clear, self.model())))
        self.assertNotIn("Irritable bowel syndrome", names(referrals.prioritize({**self.clear, "weight_loss": "unknown"}, self.model())))

    def test_mimics_and_missing_tests(self):
        result = referrals.prioritize(dict(diarrhoea_weeks=8, celiac_serology="positive"), self.model(NSAID_use_times_month=3))
        names = {c["condition"] for c in result["consider"]}
        self.assertEqual(names, {"Celiac disease", "NSAID-related intestinal injury"})
        self.assertIn("Stool culture and C. difficile test", result["missing_tests"])

    def test_output_never_contains_a_probability(self):
        self.assertNotIn("probability", str(referrals.prioritize(self.clear, self.model())).lower())


class CareBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        raw = load_raw()
        cls.row = raw[raw.synthetic_IBD_outcome == 1].iloc[0]
        cls.patient = Patient.objects.create(patient_code=cls.row.patient_id, source="synthetic", synthetic_label=1,
                                             data={f: _py(cls.row[f]) for f in FEATURES})
        cls.user = get_user_model().objects.create_user("nurse", password="pw")

    def setUp(self):
        self.client.login(username="nurse", password="pw")

    def plan(self, status="at_risk"):
        return MonitoringPlan.objects.create(patient=self.patient, care_status=status, next_due=care.today())


class ReassessmentTests(CareBase):
    def test_kind_and_prediction_are_unchanged(self):
        first = care.record_assessment(self.patient)
        second = care.record_assessment(self.patient)
        self.assertEqual((first.kind, second.kind), ("initial", "reassessment"))
        self.assertAlmostEqual(second.probability, predict_ibd(self.patient.data)["probability"], places=3)

    def test_edit_form_round_trip_keeps_values(self):
        form = PatientEditForm(patient=self.patient)
        self.assertNotIn("patient_code", form.fields)
        data = {name: field.initial for name, field in form.fields.items()}
        bound = PatientEditForm(data, patient=self.patient)
        self.assertTrue(bound.is_valid(), bound.errors)
        self.assertEqual(bound.patient_data(), self.patient.data)

    def test_edit_cannot_change_patient_id(self):
        form = PatientEditForm(patient=self.patient)
        data = {name: field.initial for name, field in form.fields.items()}
        data.update(patient_code="HACKED", CRP_mg_L=9)
        response = self.client.post(reverse("patient_edit", args=[self.patient.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.patient_code, self.row.patient_id)
        self.assertEqual(self.patient.data["CRP_mg_L"], 9)
        self.assertIsNone(self.patient.synthetic_label)

    def test_earlier_assessment_keeps_its_saved_values(self):
        first = care.record_assessment(self.patient)
        saved = first.inputs["CRP_mg_L"]
        form = PatientEditForm(patient=self.patient)
        data = {name: field.initial for name, field in form.fields.items()}
        data.update(CRP_mg_L=11.5, reassess="1")
        response = self.client.post(reverse("patient_edit", args=[self.patient.pk]), data)
        latest = care.latest_assessment(self.patient)
        self.assertRedirects(response, reverse("result", args=[latest.pk]))
        first.refresh_from_db()
        self.assertEqual(first.inputs["CRP_mg_L"], saved)
        self.assertEqual(latest.inputs["CRP_mg_L"], 11.5)

    def test_future_or_reversed_treatment_dates_are_rejected(self):
        url = reverse("treatment_add", args=[self.patient.pk])
        tomorrow = care.today() + timedelta(days=1)
        self.client.post(url, {"medication": "X", "start_date": tomorrow})
        self.client.post(url, {"medication": "X", "start_date": care.today(), "end_date": care.today() - timedelta(days=1)})
        self.assertFalse(TreatmentEvent.objects.exists())

    def test_since_treatment_reports_changes_without_claiming_effect(self):
        baseline = care.record_assessment(self.patient)
        Assessment.objects.filter(pk=baseline.pk).update(created=baseline.created - timedelta(weeks=8))
        TreatmentEvent.objects.create(patient=self.patient, medication="Demo", start_date=care.today() - timedelta(weeks=6))
        self.patient.data = {**self.patient.data, "CRP_mg_L": 0.9}
        self.patient.save()
        latest = care.record_assessment(self.patient)
        self.assertEqual(latest.treatment.medication, "Demo")
        summary = care.since_treatment(latest)
        self.assertEqual(summary["baseline"].pk, baseline.pk)
        self.assertEqual(summary["weeks"], 6)
        page = self.client.get(reverse("result", args=[latest.pk]))
        self.assertContains(page, "do not show whether the medication worked")
        self.assertNotContains(page, "treatment effective")

    def test_no_comparison_without_a_pre_treatment_assessment(self):
        TreatmentEvent.objects.create(patient=self.patient, medication="Demo", start_date=care.today())
        self.assertIsNone(care.since_treatment(care.record_assessment(self.patient)))

    def test_ended_treatment_is_not_linked(self):
        TreatmentEvent.objects.create(patient=self.patient, medication="Old", start_date=care.today() - timedelta(weeks=9),
                                      end_date=care.today() - timedelta(weeks=1))
        self.assertIsNone(care.record_assessment(self.patient).treatment)


class MonitoringTests(CareBase):
    def worsen(self):
        self.patient.data = {**self.patient.data, "fecal_calprotectin_ug_g": 400, "CRP_mg_L": 9,
                             "perianal_fistula_history": 1, "recurrent_aphthous_ulcers": 1}
        self.patient.save()

    def start_low(self):
        self.patient.data = {**self.patient.data, "fecal_calprotectin_ug_g": 60, "CRP_mg_L": 1,
                             "perianal_fistula_history": 0, "recurrent_aphthous_ulcers": 0}
        self.patient.save()

    def add_alert(self, assessment, rule_id, severity):
        return Alert.objects.create(patient=self.patient, assessment=assessment, rule_id=rule_id, severity=severity,
                                    rules_version=rules.RULES_VERSION, title=rule_id, detail="d", source="s")

    def test_short_dashboard_list_cannot_hide_an_urgent_alert(self):
        assessment = care.record_assessment(self.patient)
        urgent = self.add_alert(assessment, "older_urgent", "urgent")
        for n in range(6):
            self.add_alert(assessment, f"newer_review_{n}", "review")
        for url in (reverse("dashboard"), reverse("alerts")):
            with self.subTest(url=url):
                response = self.client.get(url)
                rows = response.context["open_alerts"] if url == reverse("dashboard") else response.context["page"]
                self.assertEqual(list(rows)[0], urgent)

    def test_unmonitored_patients_get_no_alerts(self):
        self.start_low()
        care.record_assessment(self.patient)
        self.worsen()
        care.record_assessment(self.patient)
        self.assertFalse(Alert.objects.exists())

    def test_alerts_fire_once_and_can_be_resolved(self):
        self.plan()
        self.start_low()
        care.record_assessment(self.patient)
        self.worsen()
        care.record_assessment(self.patient)
        fired = set(Alert.objects.values_list("rule_id", flat=True))
        self.assertTrue({"calprotectin_cross", "crp_cross", "new_red_flag"} <= fired)
        count = Alert.objects.count()
        self.start_low()
        care.record_assessment(self.patient)
        self.worsen()
        care.record_assessment(self.patient)
        self.assertEqual(Alert.objects.count(), count, "open alerts must not be duplicated")
        alert = Alert.objects.get(rule_id="new_red_flag")
        self.client.post(reverse("alert_action", args=[alert.pk]), {"status": "resolved", "note": "Reviewed"})
        alert.refresh_from_db()
        self.assertEqual((alert.status, alert.note, alert.acted_by), ("resolved", "Reviewed", self.user))

    def test_saving_an_assessment_moves_the_next_review(self):
        plan = self.plan()
        care.record_assessment(self.patient)
        plan.refresh_from_db()
        self.assertEqual(plan.next_due, care.today() + timedelta(weeks=plan.review_interval_weeks))

    def test_overdue_is_computed_without_writes(self):
        plan = self.plan()
        MonitoringPlan.objects.filter(pk=plan.pk).update(next_due=care.today() - timedelta(days=1))
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("alerts"))
        self.assertContains(response, self.patient.patient_code)
        writes = [q["sql"] for q in queries if "clinic_" in q["sql"]
                  and q["sql"].lstrip().upper().startswith(("INSERT", "DELETE", "UPDATE"))]
        self.assertEqual(writes, [])

    def test_monitoring_form_starts_a_plan(self):
        self.client.post(reverse("monitoring_update", args=[self.patient.pk]),
                         {"care_status": "diagnosed", "review_interval_weeks": 6, "active": "on"})
        plan = MonitoringPlan.objects.get(patient=self.patient)
        self.assertEqual((plan.care_status, plan.next_due), ("diagnosed", care.today() + timedelta(weeks=6)))

    def test_changing_the_interval_moves_the_next_review(self):
        plan = self.plan()
        url = reverse("monitoring_update", args=[self.patient.pk])
        self.client.post(url, {"care_status": "at_risk", "review_interval_weeks": 4, "active": "on"})
        plan.refresh_from_db()
        self.assertEqual(plan.next_due, care.today() + timedelta(weeks=4))

    def test_rules_are_published_on_the_about_page(self):
        response = self.client.get(reverse("settings"))
        self.assertContains(response, rules.RULES_VERSION)
        self.assertContains(response, referrals.RULES_VERSION)


class ReferralPageTests(CareBase):
    form = dict(rectal_bleeding="unknown", abdominal_pain="yes", nocturnal_symptoms="unknown", weight_loss="unknown",
                abdominal_or_rectal_mass="unknown", recent_gastroenteritis_or_travel="unknown", iron_deficiency="unknown",
                stool_infection_test="not_done", celiac_serology="positive")

    def test_flow_saves_inputs_outside_the_model_and_records_decision(self):
        assessment = care.record_assessment(self.patient)
        before = dict(self.patient.data)
        response = self.client.post(reverse("referral_new", args=[assessment.pk]), self.form)
        review = ReferralReview.objects.get()
        self.assertRedirects(response, reverse("referral", args=[review.pk]))
        self.assertEqual(review.rules_version, referrals.RULES_VERSION)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.data, before)
        page = self.client.get(reverse("referral", args=[review.pk]))
        self.assertContains(page, "Draft rules, pending clinical review")
        self.assertContains(page, "Celiac disease")
        url = reverse("referral_decision", args=[review.pk])
        self.client.post(url, {"decision": "changed", "decision_reason": ""})
        review.refresh_from_db()
        self.assertEqual(review.decision, "", "changing the suggestion needs a reason")
        self.client.post(url, {"decision": "changed", "decision_reason": "Clinical judgment"})
        review.refresh_from_db()
        self.assertEqual((review.decision, review.decided_by), ("changed", self.user))

    def test_never_narrated_variables_stay_out_of_review_output(self):
        assessment = care.record_assessment(self.patient)
        review = care.create_referral_review(assessment, self.form)
        text = str(review.result)
        for name in NO_NARRATE:
            self.assertNotIn(name, text)


class AccessTests(CareBase):
    def test_every_new_page_requires_login(self):
        assessment = care.record_assessment(self.patient)
        review = care.create_referral_review(assessment, {})
        urls = [reverse("alerts"), reverse("patient_edit", args=[self.patient.pk]),
                reverse("referral_new", args=[assessment.pk]), reverse("referral", args=[review.pk])]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_state_changing_urls_reject_get(self):
        for name in ("treatment_add", "monitoring_update"):
            self.assertEqual(self.client.get(reverse(name, args=[self.patient.pk])).status_code, 405, name)


class PagesRenderTests(CareBase):
    def test_patient_care_section_dashboard_and_result_render(self):
        self.plan("diagnosed")
        assessment = care.record_assessment(self.patient)
        self.assertEqual(self.client.get(reverse("patient", args=[self.patient.pk]), {"section": "care"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.assertContains(self.client.get(reverse("result", args=[assessment.pk])), "Referral prioritization")


class SeedTests(TestCase):
    def test_seed_is_repeatable_and_builds_each_scenario(self):
        call_command("seed_demo_scenarios", stdout=StringIO())
        call_command("seed_demo_scenarios", stdout=StringIO())
        self.assertEqual(Patient.objects.filter(patient_code__startswith="DEMO-").count(), 3)
        at_risk = Patient.objects.get(patient_code="DEMO-ATRISK-01")
        self.assertEqual(at_risk.assessments.count(), 2)
        titles = list(at_risk.alerts.values_list("title", flat=True))
        self.assertTrue(titles and all("Possible progression" in t for t in titles))
        treated = Patient.objects.get(patient_code="DEMO-TREATED-01")
        self.assertIsNotNone(care.since_treatment(care.latest_assessment(treated)))
        self.assertTrue(care.overdue_plans().filter(patient=treated).exists())
        review = Patient.objects.get(patient_code="DEMO-REFERRAL-01").referral_reviews.get()
        self.assertEqual(review.result["priority"], "soon")


class MigrationTests(TestCase):
    def test_models_and_migrations_agree(self):
        call_command("makemigrations", "clinic", check=True, dry_run=True, stdout=StringIO())


class FormCompatibilityTests(CareBase):
    def test_add_patient_form_still_requires_no_id(self):
        form = PatientForm()
        data = {name: field.initial for name, field in form.fields.items()}
        self.assertTrue(PatientForm(data).is_valid())
