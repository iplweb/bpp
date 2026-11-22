from django.conf import settings
from django.urls import reverse


def bpp_configuration(request):
    from bpp.favicon_wersja import wersja as favicon_wersja
    from bpp.models.abstract import POLA_PUNKTACJI
    from bpp.models.motyw_wlasny import MOTYW_WLASNY, MotywWlasny
    from bpp.przymiarka_motywu import aktywna as przymiarka_aktywna

    uczelnia = getattr(request, "_uczelnia", None)
    if uczelnia and hasattr(uczelnia, "theme_name") and uczelnia.theme_name:
        theme = uczelnia.theme_name
    else:
        theme = settings.THEME_NAME

    # Motyw z konfiguratora wyglądu: CSS z bazy (bpp:motyw_wlasny_css),
    # dołączany w bare.html poza {% compress %}. Bez zapisanego motywu —
    # motyw domyślny.
    motyw_wlasny_url = None
    if theme == MOTYW_WLASNY:
        skrot = MotywWlasny.skrot_dla(uczelnia.pk) if uczelnia else None
        if skrot:
            motyw_wlasny_url = reverse("bpp:motyw_wlasny_css", args=(skrot,))
        else:
            theme = settings.THEME_NAME

    # Tryb podglądu konfiguratora wyglądu: strona w ramce konfiguratora
    # dostaje pusty <style>, do którego konfigurator wstawia skompilowany
    # motyw (bare.html). Tylko dla obsługi — zwykły użytkownik zawsze widzi
    # motyw uczelni.
    user = getattr(request, "user", None)
    podglad_motywu = bool(
        request is not None
        and "podglad_motywu" in request.GET
        and user is not None
        and user.is_staff
    )

    # Przymiarka (tylko ta sesja obsługi) wygrywa z motywem uczelni.
    przymiarka = przymiarka_aktywna(request) if request is not None else None
    if przymiarka:
        motyw_wlasny_url = reverse("bpp:motyw_przymiarka_css", args=(przymiarka,))

    return {
        "PODGLAD_MOTYWU": podglad_motywu,
        "PRZYMIARKA_MOTYWU": bool(przymiarka) and not podglad_motywu,
        "FAVICON_WERSJA": favicon_wersja(),
        "MOTYW_WLASNY_URL": motyw_wlasny_url,
        "THEME_NAME": "scss/" + theme + ".css",
        "THEME_NAME_RAW": theme,
        "ENABLE_NEW_REPORTS": settings.ENABLE_NEW_REPORTS,
        "MAX_NO_AUTHORS_ON_BROWSE_JEDNOSTKA_PAGE": settings.MAX_NO_AUTHORS_ON_BROWSE_JEDNOSTKA_PAGE,
        "BPP_POLA_PUNKTACJI": POLA_PUNKTACJI,
        "DJANGO_BPP_ENABLE_TEST_CONFIGURATION": getattr(
            settings, "DJANGO_BPP_ENABLE_TEST_CONFIGURATION", False
        ),
    }
