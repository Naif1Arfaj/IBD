from django.urls import path

from . import care_views, views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("patients/", views.patients, name="patients"),
    path("patients/new/", views.patient_new, name="patient_new"),
    path("patients/<int:pk>/", views.patient, name="patient"),
    path("patients/<int:pk>/assess/", views.assess, name="assess"),
    path("patients/<int:pk>/edit/", care_views.patient_edit, name="patient_edit"),
    path("patients/<int:pk>/treatments/add/", care_views.treatment_add, name="treatment_add"),
    path("patients/<int:pk>/monitoring/", care_views.monitoring_update, name="monitoring_update"),
    path("alerts/", care_views.alerts, name="alerts"),
    path("alerts/<int:pk>/action/", care_views.alert_action, name="alert_action"),
    path("assessments/<int:pk>/referral/", care_views.referral_new, name="referral_new"),
    path("referrals/<int:pk>/", care_views.referral, name="referral"),
    path("referrals/<int:pk>/decision/", care_views.referral_decision, name="referral_decision"),
    path("assessments/", views.assessments, name="assessments"),
    path("assessments/<int:pk>/", views.result, name="result"),
    path("assessments/<int:pk>/report/", views.report_create, name="report_create"),
    path("reports/", views.reports, name="reports"),
    path("reports/<int:pk>/", views.report, name="report"),
    path("evidence/", views.evidence, name="evidence"),
    path("papers/<path:file>", views.paper, name="paper"),
    path("settings/", views.settings_page, name="settings"),
]
