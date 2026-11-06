from django.conf import settings


def branding(request):
    context = {"HOSPITAL_NAME": settings.HOSPITAL_NAME, "HOSPITAL_SUBTITLE": settings.HOSPITAL_SUBTITLE}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        from .models import Alert
        context["open_alert_count"] = Alert.objects.filter(status="open").count()
    return context
