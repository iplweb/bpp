from django.conf import settings


def bpp_configuration(request):
    from bpp.models.abstract import POLA_PUNKTACJI

    uczelnia = getattr(request, "_uczelnia", None)
    if uczelnia and hasattr(uczelnia, "theme_name") and uczelnia.theme_name:
        theme = uczelnia.theme_name
    else:
        theme = settings.THEME_NAME

    return {
        "THEME_NAME": "scss/" + theme + ".css",
        "THEME_NAME_RAW": theme,
        "ENABLE_NEW_REPORTS": settings.ENABLE_NEW_REPORTS,
        "MAX_NO_AUTHORS_ON_BROWSE_JEDNOSTKA_PAGE": settings.MAX_NO_AUTHORS_ON_BROWSE_JEDNOSTKA_PAGE,
        "BPP_POLA_PUNKTACJI": POLA_PUNKTACJI,
        "DJANGO_BPP_ENABLE_TEST_CONFIGURATION": getattr(
            settings, "DJANGO_BPP_ENABLE_TEST_CONFIGURATION", False
        ),
    }
