from django.conf import settings


def testing(request):
    """
    Provides the TESTING setting to templates.
    """
    return {
        "TESTING": getattr(settings, "TESTING", False),
    }
