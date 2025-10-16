from django.conf import settings


def bpp_configuration(request):
    from bpp.models.abstract import POLA_PUNKTACJI

    return {
        "THEME_NAME": "scss/" + settings.THEME_NAME + ".css",
        "THEME_NAME_RAW": settings.THEME_NAME,
        "ENABLE_NEW_REPORTS": settings.ENABLE_NEW_REPORTS,
        "MAX_NO_AUTHORS_ON_BROWSE_JEDNOSTKA_PAGE": settings.MAX_NO_AUTHORS_ON_BROWSE_JEDNOSTKA_PAGE,
        "BPP_POLA_PUNKTACJI": POLA_PUNKTACJI,
        "DJANGO_BPP_ENABLE_TEST_CONFIGURATION": getattr(
            settings, "DJANGO_BPP_ENABLE_TEST_CONFIGURATION", False
        ),
    }
