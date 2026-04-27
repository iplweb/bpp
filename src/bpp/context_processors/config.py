from django.conf import settings


def bpp_configuration(request):
    from bpp.models.abstract import POLA_PUNKTACJI

    # THEME_NAME format is "app-{blue|green|orange}". Tailwind builds live
    # under tailwind/dist/{blue|green|orange}.css (see Gruntfile.js
    # shell:tailwind* tasks). Strip the "app-" prefix to derive the
    # Tailwind path; fall back to "blue" for legacy theme names so a typo
    # in env doesn't 500 the page.
    theme_color = settings.THEME_NAME.removeprefix("app-") or "blue"

    return {
        "THEME_NAME": "scss/" + settings.THEME_NAME + ".css",
        "THEME_NAME_RAW": settings.THEME_NAME,
        "TAILWIND_THEME_NAME": f"tailwind/dist/{theme_color}.css",
        "ENABLE_NEW_REPORTS": settings.ENABLE_NEW_REPORTS,
        "MAX_NO_AUTHORS_ON_BROWSE_JEDNOSTKA_PAGE": settings.MAX_NO_AUTHORS_ON_BROWSE_JEDNOSTKA_PAGE,
        "BPP_POLA_PUNKTACJI": POLA_PUNKTACJI,
        "DJANGO_BPP_ENABLE_TEST_CONFIGURATION": getattr(
            settings, "DJANGO_BPP_ENABLE_TEST_CONFIGURATION", False
        ),
    }
