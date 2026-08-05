"""Centralna bramka autoryzacji dla operacji redaktorskich (wprowadzanie
danych).

Problem, który to zamyka: w wielu widokach ``login_required`` /
``LoginRequiredMixin`` było traktowane jak uprawnienie redaktorskie. Samo
zalogowanie to jednak *uwierzytelnienie*, nie *autoryzacja* — zwykłe konto
(bez ``is_staff``, bez grup) mogło wywoływać operacje mutujące dane globalne.

Jedno źródło prawdy, domyślnie odmawiające dostępu, w trzech formach:

- :func:`moze_wprowadzac_dane` — predykat (superuser LUB grupa
  ``GR_WPROWADZANIE_DANYCH``),
- :class:`WprowadzanieDanychRequiredMixin` — dla widoków klasowych,
- :func:`wprowadzanie_danych_wymagane` — dekorator dla widoków funkcyjnych.

Semantyka statusów (celowo, spójnie w mixinie i dekoratorze):

- anonim → 302 na stronę logowania (kontrakt ``LoginRequiredMixin``),
- zalogowany-bez-uprawnień → 403 (``PermissionDenied``),
- uprawniony → normalna odpowiedź widoku.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import URLPattern, URLResolver

from bpp.const import GR_WPROWADZANIE_DANYCH

_KOMUNIKAT = "Brak uprawnień do wprowadzania danych."


def moze_wprowadzac_dane(user) -> bool:
    """Czy ``user`` ma pełne uprawnienia redaktorskie: superuser lub członek
    grupy ``GR_WPROWADZANIE_DANYCH``. Anonim / zwykły użytkownik → ``False``."""
    return bool(
        user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
        )
    )


class WprowadzanieDanychRequiredMixin(LoginRequiredMixin):
    """Mixin dla CBV: anonim → login redirect; zalogowany-bez-uprawnień → 403.

    Kolejność ma znaczenie: dla anonima delegujemy do ``LoginRequiredMixin``
    (przekierowanie na login), a dopiero dla zalogowanych, ale bez uprawnień,
    podnosimy ``PermissionDenied`` (403).
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not moze_wprowadzac_dane(request.user):
            raise PermissionDenied(_KOMUNIKAT)
        return super().dispatch(request, *args, **kwargs)


def wprowadzanie_danych_wymagane(view_func):
    """Dekorator dla FBV z tą samą semantyką co
    :class:`WprowadzanieDanychRequiredMixin`."""

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not moze_wprowadzac_dane(request.user):
            raise PermissionDenied(_KOMUNIKAT)
        return view_func(request, *args, **kwargs)

    return _wrapped


def wymagaj_wprowadzania_danych_dla_urlpatterns(urlpatterns):
    """Owija (rekurencyjnie, in-place) każdy wzorzec URL dekoratorem
    :func:`wprowadzanie_danych_wymagane`.

    Służy do bramkowania *całej* aplikacji redaktorskiej na poziomie URLconf —
    dzięki temu każdy nowy widok jest chroniony domyślnie, bez pamiętania o
    dekoratorze na pojedynczej funkcji. Zwraca tę samą listę (dla wygody
    ``urlpatterns = wymagaj_...([...])``).
    """
    for wzorzec in urlpatterns:
        if isinstance(wzorzec, URLResolver):
            wymagaj_wprowadzania_danych_dla_urlpatterns(wzorzec.url_patterns)
        elif isinstance(wzorzec, URLPattern) and wzorzec.callback is not None:
            wzorzec.callback = wprowadzanie_danych_wymagane(wzorzec.callback)
    return urlpatterns
