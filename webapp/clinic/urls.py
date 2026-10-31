from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("patients/", views.patients, name="patients"),
    path("patients/new/", views.patient_new, name="patient_new"),
    path("patients/<int:pk>/", views.patient, name="patient"),
    path("patients/<int:pk>/assess/", views.assess, name="assess"),
    path("assessments/", views.assessments, name="assessments"),
    path("assessments/<int:pk>/", views.result, name="result"),
    path("assessments/<int:pk>/report/", views.report_create, name="report_create"),
    path("reports/", views.reports, name="reports"),
    path("reports/<int:pk>/", views.report, name="report"),
    path("evidence/", views.evidence, name="evidence"),
    path("papers/<path:file>", views.paper, name="paper"),
    path("settings/", views.settings_page, name="settings"),
]
