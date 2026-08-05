from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission

from bpp.const import GR_RAPORTY_WYSWIETLANIE
from bpp.models import Uczelnia
from bpp.views.zapytanie import user_can_use_query_editor


class ApiV1Wlaczone(BasePermission):
    """Bramka CAŁEGO ``/api/v1/`` — przełącznik ``Uczelnia.api_v1_wlaczone``.

    Świadomie NIE zwraca ``False``: to dałoby 401/403, czyli komunikat
    „endpoint istnieje, tylko nie dla ciebie". Wyłączone API ma wyglądać na
    nieistniejące, więc podnosimy ``NotFound`` (404, treść content-negotiated
    przez DRF).

    Rozstrzyganie tenanta idzie przez ``Uczelnia.objects.get_for_request`` —
    ta sama droga, co reszta polityk widoczności API (``viewsets/common.py``,
    ``scoping.py``). Gdy uczelni nie ma (pusta baza, kreator konfiguracji,
    brak mapowania Site→Uczelnia) resolver zwraca ``None`` — wtedy NIE
    blokujemy, bo nie ma kto podjąć decyzji, a dotychczasowe zachowanie
    (API działa) musi zostać zachowane.
    """

    def has_permission(self, request, view):
        uczelnia = Uczelnia.objects.get_for_request(request)
        if uczelnia is not None and not uczelnia.api_v1_wlaczone:
            raise NotFound()
        return True


class BramkaApiV1Mixin:
    """Dokleja :class:`ApiV1Wlaczone` na początek uprawnień widoku.

    Przez ``get_permissions()``, a nie przez ``permission_classes`` — dzięki
    temu nie kasujemy deklaracji widoku (np. ``MoznaUzywacZapytania``
    w ``/zapytanie/``, ``IsGrupaRaportyWyswietlanie`` w raporcie slotów),
    a bramka i tak jest sprawdzana jako pierwsza.
    """

    def get_permissions(self):
        return [ApiV1Wlaczone(), *super().get_permissions()]


def z_bramka_api_v1(view_cls):
    """Zwróć podklasę ``view_cls`` objętą bramką ``api_v1_wlaczone``.

    Podklasa, a nie mutacja ``view_cls`` w miejscu: viewsety bywają
    importowane i testowane bezpośrednio, a klasa ``WhoAmIView`` należy do
    innej aplikacji — doklejanie im uprawnień „z zewnątrz" byłoby zmianą
    globalną, widoczną poza ``/api/v1/``. Podklasa dotyczy wyłącznie tego,
    co realnie wisi pod tym prefiksem.
    """
    return type(
        view_cls.__name__,
        (BramkaApiV1Mixin, view_cls),
        {"__module__": view_cls.__module__, "__doc__": view_cls.__doc__},
    )


class IsGrupaRaportyWyswietlanie(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_superuser or (
            GR_RAPORTY_WYSWIETLANIE
            in request.user.groups.values_list("name", flat=True)
        )


class MoznaUzywacZapytania(BasePermission):
    """Dostęp do DjangoQL po API = ten sam kontrakt co web-edytor:
    superuser albo staff w grupie „wprowadzanie danych"."""

    message = (
        "Wymagane konto redaktora (staff w grupie 'wprowadzanie danych') "
        "lub superusera."
    )

    def has_permission(self, request, view):
        return user_can_use_query_editor(request.user)
