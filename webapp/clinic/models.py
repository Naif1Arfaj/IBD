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


class TreatmentEvent(models.Model):
    """A recorded medication, so later assessments can be reviewed against its start date."""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="treatments")
    medication = models.CharField(max_length=120)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=300, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date", "-pk"]

    def __str__(self):
        return f"{self.medication} ({self.start_date})"


class Assessment(models.Model):
    KIND_CHOICES = [("initial", "Initial assessment"), ("reassessment", "Reassessment")]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="assessments")
    kind = models.CharField(max_length=14, choices=KIND_CHOICES, default="initial")
    treatment = models.ForeignKey(TreatmentEvent, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="assessments")
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


class MonitoringPlan(models.Model):
    """Follow-up for an at-risk (preclinical) or diagnosed patient."""
    CARE_STATUS_CHOICES = [("at_risk", "At risk (no IBD diagnosis)"), ("diagnosed", "Diagnosed IBD")]

    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name="monitoring")
    care_status = models.CharField(max_length=10, choices=CARE_STATUS_CHOICES, default="at_risk")
    review_interval_weeks = models.PositiveSmallIntegerField(default=12)
    next_due = models.DateField()
    active = models.BooleanField(default=True)
    started_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["next_due", "pk"]


class Alert(models.Model):
    SEVERITY_CHOICES = [("urgent", "Urgent"), ("review", "Review")]
    STATUS_CHOICES = [("open", "Open"), ("acknowledged", "Acknowledged"), ("resolved", "Resolved")]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="alerts")
    assessment = models.ForeignKey(Assessment, null=True, blank=True, on_delete=models.SET_NULL, related_name="alerts")
    rule_id = models.CharField(max_length=30)
    rules_version = models.CharField(max_length=30)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="review")
    title = models.CharField(max_length=160)
    detail = models.CharField(max_length=400)
    source = models.CharField(max_length=400, blank=True)
    status = models.CharField(max_length=14, choices=STATUS_CHOICES, default="open")
    note = models.CharField(max_length=300, blank=True)
    acted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    acted_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["patient", "rule_id"], condition=models.Q(status="open"),
                                    name="one_open_alert_per_patient_rule"),
        ]


class ReferralReview(models.Model):
    """A rule-based referral suggestion and the clinician's decision about it."""
    DECISION_CHOICES = [("accepted", "Accepted"), ("changed", "Changed"), ("not_needed", "Not needed")]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="referral_reviews")
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="referral_reviews")
    inputs = models.JSONField(help_text="Symptoms and tests, kept separate from the 61 model inputs.")
    result = models.JSONField()
    rules_version = models.CharField(max_length=30)
    decision = models.CharField(max_length=12, choices=DECISION_CHOICES, blank=True)
    decision_reason = models.CharField(max_length=300, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="referral_decisions")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="referral_reviews")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created", "-pk"]
