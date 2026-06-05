"""Reguła: czy bieżący request ma używać logowania OIDC.

W instalacji wielouczelnianej jeden proces obsługuje wiele uczelni (po
domenie), ale OIDC to **jeden realm na proces** (``mozilla-django-oidc`` czyta
globalne ``OIDC_RP_*``). Dlatego logowanie OIDC pokazujemy/uruchamiamy tylko na
domenie uczelni, do której ten realm należy — identyfikowanej przez
``OIDC_LOGIN_SKROT`` (== ``Uczelnia.skrot``).

Jedna funkcja (`oidc_enabled_for_request`) jest wspólnym źródłem prawdy dla
menu (context processor) i routingu (`login_form`), żeby nie rozjechało się to,
co widać, z tym, dokąd faktycznie kieruje logowanie.
"""

from django.conf import settings


def oidc_enabled_for_request(request):
    """Czy ``request`` (jego uczelnia) ma używać logowania OIDC.

    * OIDC wyłączone w procesie → ``False``.
    * Brak ``OIDC_LOGIN_SKROT`` (konfiguracja bez skrótu = instalacja
      jedno-uczelniana) → ``True`` globalnie, jak dawniej.
    * Skrót ustawiony → ``True`` tylko gdy uczelnia z requestu ma ten skrót.
    """
    if not getattr(settings, "OIDC_LOGIN_ENABLED", False):
        return False

    skrot = (getattr(settings, "OIDC_LOGIN_SKROT", "") or "").strip()
    if not skrot:
        # Brak per-uczelnia bindingu — pojedyncza uczelnia, OIDC globalnie.
        return True

    from bpp.models import Uczelnia

    uczelnia = Uczelnia.objects.get_for_request(request)
    if uczelnia is None:
        return False
    return (uczelnia.skrot or "").strip().upper() == skrot.upper()
