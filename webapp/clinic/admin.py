from django.contrib import admin

from .models import Alert, Assessment, EvidenceSummary, MonitoringPlan, Patient, ReferralReview, Report, TreatmentEvent


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("patient_code", "source", "age", "sex", "synthetic_label", "created")
    list_filter = ("source", "synthetic_label")
    search_fields = ("patient_code",)


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("patient", "prediction", "tier", "probability", "model_name", "created")
    list_filter = ("tier", "prediction")


admin.site.register(Report)
admin.site.register(EvidenceSummary)
admin.site.register(TreatmentEvent)
admin.site.register(MonitoringPlan)
admin.site.register(Alert)
admin.site.register(ReferralReview)
