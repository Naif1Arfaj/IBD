from django.conf import settings


def branding(request):
    return {"HOSPITAL_NAME": settings.HOSPITAL_NAME, "HOSPITAL_SUBTITLE": settings.HOSPITAL_SUBTITLE}
