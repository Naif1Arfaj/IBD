import json
from pathlib import Path
from unittest import mock

from django.db import connection
from django.test import SimpleTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from features import GROUPS
from predict import predict_ibd

from . import care, microbiome
from .models import Assessment
from .tests import Base

INPUTS = GROUPS["Microbiome diversity"]


class ReferenceFileTests(SimpleTestCase):
    def setUp(self):
        self.ref = json.loads(microbiome.REFERENCE_PATH.read_text(encoding="utf-8"))

    def test_covers_every_input_and_group(self):
        self.assertEqual(list(self.ref["features"]), INPUTS)
        for entry in self.ref["features"].values():
            self.assertEqual(set(entry["groups"]), {"nonIBD", "CD", "UC"})

    def test_percentiles_are_ordered(self):
        for entry in self.ref["features"].values():
            for g in entry["groups"].values():
                points = [g[f"p{p}"] for p in self.ref["percentiles"]]
                self.assertEqual(points, sorted(points))

    def test_no_person_is_counted_twice(self):
        # One median per person: a group's count can never exceed its number of people, whatever the samples.
        people = self.ref["cohort"]["people"]
        self.assertEqual(people, {"nonIBD": 27, "CD": 65, "UC": 38})
        self.assertLess(sum(people.values()), self.ref["cohort"]["samples"])
        for entry in self.ref["features"].values():
            for key, g in entry["groups"].items():
                self.assertLessEqual(g["people"], people[key])

    def test_abundances_are_percent_not_fractions(self):
        self.assertGreater(self.ref["features"]["Bacteroides_abundance_pct"]["groups"]["nonIBD"]["p50"], 1)

    def test_every_source_is_hashed(self):
        self.assertEqual(len(self.ref["sources"]), 4)
        for source in self.ref["sources"]:
            self.assertEqual(len(source["sha256"]), 64)

    def test_downloaded_files_are_not_committed_paths(self):
        ignored = (Path(microbiome.settings.IBD_ROOT) / ".gitignore").read_text()
        self.assertIn("data/ibdmdb/", ignored)


class RangeRowTests(SimpleTestCase):
    def row(self, feature, value):
        rows = microbiome.patient_ranges({feature: value})["rows"]
        return next(r for r in rows if r["feature"] == feature)

    def test_all_inputs_have_a_row_and_three_groups(self):
        rows = microbiome.patient_ranges({})["rows"]
        self.assertEqual([r["feature"] for r in rows], INPUTS)
        for row in rows:
            self.assertEqual([g["people"] > 0 for g in row["groups"]], [True, True, True])

    def test_missing_or_invalid_value_has_no_marker(self):
        for value in (None, "", "unknown"):
            row = self.row("Roseburia_abundance_pct", value)
            self.assertIsNone(row["value"])
            self.assertIsNone(row["marker"])
            self.assertEqual(row["outside"], "")

    def test_outside_note_only_beyond_all_groups(self):
        self.assertIn("Above", self.row("alpha_diversity_Shannon", 5.0)["outside"])
        self.assertIn("Below", self.row("alpha_diversity_Shannon", 1.0)["outside"])
        self.assertEqual(self.row("alpha_diversity_Shannon", 2.5)["outside"], "")

    def test_positions_stay_on_the_axis(self):
        for feature, value in (("Firmicutes_Bacteroidetes_ratio", 0), ("Firmicutes_Bacteroidetes_ratio", 500),
                               ("Proteobacteria_abundance_pct", 90), ("Faecalibacterium_abundance_pct", 0)):
            row = self.row(feature, value)
            self.assertTrue(0 <= row["marker"] <= 100)
            for g in row["groups"]:
                self.assertTrue(0 <= g["left"] and g["left"] + g["width"] <= 100.01)
                self.assertTrue(0 <= g["median"] <= 100)

    def test_ratio_uses_log_scale_so_most_people_stay_visible(self):
        row = self.row("Firmicutes_Bacteroidetes_ratio", 1.0)
        self.assertTrue(row["is_log"])
        self.assertGreater(row["groups"][0]["box_width"], 5)

    def test_missing_reference_file_hides_the_panel(self):
        microbiome.reference.cache_clear()
        self.addCleanup(microbiome.reference.cache_clear)
        with mock.patch.object(microbiome, "REFERENCE_PATH", Path("/nonexistent/reference.json")):
            self.assertIsNone(microbiome.patient_ranges({}))
            self.assertIsNone(microbiome.about_summary())


class PageTests(Base):
    def setUp(self):
        super().setUp()
        self.patient = self.rows[1]
        self.assessment = care.record_assessment(self.patient, self.user)

    def test_panel_is_on_patient_and_result_pages(self):
        for url in (reverse("patient", args=[self.patient.pk]) + "?section=clinical",
                    reverse("result", args=[self.assessment.pk])):
            response = self.client.get(url)
            self.assertContains(response, "microbiome-ranges")
            self.assertContains(response, "must not be used to suggest a diagnosis")
            self.assertContains(response, "27 people")

    def test_result_uses_values_saved_with_the_assessment(self):
        self.patient.data = {**self.patient.data, "alpha_diversity_Shannon": 2.5}
        self.patient.save(update_fields=["data"])
        saved = microbiome.patient_ranges(self.assessment.inputs)["rows"][0]["value"]
        response = self.client.get(reverse("result", args=[self.assessment.pk]))
        self.assertContains(response, f"This patient: {saved}")

    def test_about_page_summarises_real_data(self):
        response = self.client.get(reverse("settings"))
        self.assertContains(response, "Real microbiome reference data")
        self.assertContains(response, "false AUC")
        self.assertContains(response, "Lloyd-Price")

    def test_get_performs_no_writes(self):
        with CaptureQueriesContext(connection) as queries:
            self.client.get(reverse("result", args=[self.assessment.pk]))
            self.client.get(reverse("patient", args=[self.patient.pk]) + "?section=clinical")
            self.client.get(reverse("settings"))
        writes = [q["sql"] for q in queries if q["sql"].split()[0].upper() in ("INSERT", "UPDATE", "DELETE")
                  and "django_session" not in q["sql"]]
        self.assertEqual(writes, [])

    def test_ranges_do_not_change_the_saved_estimate(self):
        before = Assessment.objects.get(pk=self.assessment.pk).probability
        self.client.get(reverse("result", args=[self.assessment.pk]))
        self.assertEqual(Assessment.objects.get(pk=self.assessment.pk).probability, before)
        self.assertAlmostEqual(predict_ibd(self.patient.data)["probability"], before, places=3)
