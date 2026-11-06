from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("clinic", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TreatmentEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("medication", models.CharField(max_length=120)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField(blank=True, null=True)),
                ("note", models.CharField(blank=True, max_length=300)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="treatments", to="clinic.patient")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-start_date", "-pk"]},
        ),
        migrations.AddField(
            model_name="assessment",
            name="kind",
            field=models.CharField(choices=[("initial", "Initial assessment"), ("reassessment", "Reassessment")], default="initial", max_length=14),
        ),
        migrations.AddField(
            model_name="assessment",
            name="treatment",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assessments", to="clinic.treatmentevent"),
        ),
        migrations.CreateModel(
            name="MonitoringPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("care_status", models.CharField(choices=[("at_risk", "At risk (no IBD diagnosis)"), ("diagnosed", "Diagnosed IBD")], default="at_risk", max_length=10)),
                ("review_interval_weeks", models.PositiveSmallIntegerField(default=12)),
                ("next_due", models.DateField()),
                ("active", models.BooleanField(default=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("patient", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="monitoring", to="clinic.patient")),
                ("started_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["next_due", "pk"]},
        ),
        migrations.CreateModel(
            name="Alert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rule_id", models.CharField(max_length=30)),
                ("rules_version", models.CharField(max_length=30)),
                ("severity", models.CharField(choices=[("urgent", "Urgent"), ("review", "Review")], default="review", max_length=10)),
                ("title", models.CharField(max_length=160)),
                ("detail", models.CharField(max_length=400)),
                ("source", models.CharField(blank=True, max_length=400)),
                ("status", models.CharField(choices=[("open", "Open"), ("acknowledged", "Acknowledged"), ("resolved", "Resolved")], default="open", max_length=14)),
                ("note", models.CharField(blank=True, max_length=300)),
                ("acted_at", models.DateTimeField(blank=True, null=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("acted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("assessment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="alerts", to="clinic.assessment")),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="alerts", to="clinic.patient")),
            ],
            options={"ordering": ["-created", "-pk"]},
        ),
        migrations.AddConstraint(
            model_name="alert",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "open")), fields=("patient", "rule_id"), name="one_open_alert_per_patient_rule"),
        ),
        migrations.CreateModel(
            name="ReferralReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("inputs", models.JSONField(help_text="Symptoms and tests, kept separate from the 61 model inputs.")),
                ("result", models.JSONField()),
                ("rules_version", models.CharField(max_length=30)),
                ("decision", models.CharField(blank=True, choices=[("accepted", "Accepted"), ("changed", "Changed"), ("not_needed", "Not needed")], max_length=12)),
                ("decision_reason", models.CharField(blank=True, max_length=300)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("assessment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="referral_reviews", to="clinic.assessment")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="referral_reviews", to=settings.AUTH_USER_MODEL)),
                ("decided_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="referral_decisions", to=settings.AUTH_USER_MODEL)),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="referral_reviews", to="clinic.patient")),
            ],
            options={"ordering": ["-created", "-pk"]},
        ),
    ]
