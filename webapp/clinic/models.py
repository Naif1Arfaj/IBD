from django.conf import settings
from django.db import models


class Patient(models.Model):
    SOURCE_CHOICES = [("synthetic", "Synthetic dataset"), ("manual", "Entered manually")]

    patient_code = models.CharField(max_length=40, unique=True)
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES, default="manual")
    data = models.JSONField(help_text="The 61 model inputs, human-readable (e.g. 'Yes', 'Female').")
    synthetic_label = models.IntegerField(null=True, blank=True, help_text="Dataset ground truth (synthetic only).")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["patient_code"]

    def __str__(self):
        return self.patient_code

    @property
    def age(self):
        return self.data.get("age_years")

    @property
    def sex(self):
        return self.data.get("sex")


class Assessment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="assessments")
    inputs = models.JSONField()
    probability = models.FloatField()
    prediction = models.CharField(max_length=10)
    tier = models.CharField(max_length=10)
    threshold = models.FloatField()
    factors = models.JSONField(help_text="Per-variable SHAP contributions (narratable variables only).")
    group_factors = models.JSONField(help_text="SHAP summed within each of the 10 input groups.")
    model_name = models.CharField(max_length=80)
    assessed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]


class Report(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="reports")
    narrative = models.TextField(blank=True)
    narrative_refs = models.JSONField(default=list)
    evidence = models.JSONField(default=list)
    llm_used = models.BooleanField(default=False)
    notice = models.CharField(max_length=300, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]


class EvidenceSummary(models.Model):
    """Cached literature summary for one variable + effect direction."""
    feature = models.CharField(max_length=60)
    direction = models.CharField(max_length=10)
    text = models.TextField(blank=True)
    references = models.JSONField(default=list)
    llm_used = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("feature", "direction")]
