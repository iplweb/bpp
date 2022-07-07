from django.conf import settings


def theme_name(request):
    return {"THEME_NAME": "scss/" + settings.THEME_NAME + ".css"}


def enable_new_reports(request):
    return {"ENABLE_NEW_REPORTS": settings.ENABLE_NEW_REPORTS}


def max_no_authors_on_browse_jednostka_page(request):
    return {
        "MAX_NO_AUTHORS_ON_BROWSE_JEDNOSTKA_PAGE": settings.MAX_NO_AUTHORS_ON_BROWSE_JEDNOSTKA_PAGE
    }
