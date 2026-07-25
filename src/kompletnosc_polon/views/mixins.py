"""Wspólne mixiny widoków raportu kompletności danych POL-on."""

from django.urls import reverse
from django.utils.functional import cached_property

from ewaluacja_common.const import OKNO_EWALUACJI
from ewaluacja_metryki.views.mixins import (
    EwaluacjaRequiredMixin,
    ma_pelne_uprawnienia_ewaluacji,
)
from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu


class PelneUprawnieniaEwaluacjiMixin(EwaluacjaRequiredMixin):
    """Dostęp wyłącznie dla redaktorów danych.

    Raport kompletności jest narzędziem **redaktorskim**: pokazuje braki
    w cudzych rekordach i prowadzi wprost do formularza edycji w panelu
    administracyjnym. Bazowy ``EwaluacjaRequiredMixin`` przepuszcza także
    zalogowanego autora (żeby mógł obejrzeć *swoje* metryki) — tu to za mało,
    więc zawężamy test do pełnych uprawnień
    (superuser albo grupa „wprowadzanie danych”).

    Zalogowany użytkownik bez uprawnień dostanie 403 (``PermissionDenied``
    z ``AccessMixin.handle_no_permission``), niezalogowany — przekierowanie
    na formularz logowania.
    """

    def test_func(self):
        return ma_pelne_uprawnienia_ewaluacji(self.request.user)


class RaportKompletnosciMixin(PelneUprawnieniaEwaluacjiMixin):
    """Wspólny kontekst obu widoków raportu: uczelnia oglądającego i okno lat.

    Okno bierzemy ze stałej :data:`ewaluacja_common.const.OKNO_EWALUACJI` —
    jedynego źródła prawdy dla tej aplikacji. Uczelnię rozstrzyga
    :func:`raport_slotow.uczelnia_helper.uczelnia_dla_odczytu`, czyli tak samo
    jak reszta raportów slotowych (domena → Site → Uczelnia, z możliwością
    nadpisania przez superusera parametrem ``?uczelnia=<pk>``).
    """

    okno: tuple[int, int] = OKNO_EWALUACJI

    @cached_property
    def uczelnia(self):
        return uczelnia_dla_odczytu(self.request)

    def get_context_data(self, **kwargs):
        kontekst = super().get_context_data(**kwargs)
        pierwszy_rok, ostatni_rok = self.okno
        # Świadomie NIE wystawiamy tu ``uczelnia`` — pod tą nazwą base.html
        # dostaje uczelnię z context processora i nadpisanie jej wartością
        # ``None`` (instalacja bez mapowania Site→Uczelnia) wywala szablon
        # bazowy przy ``uczelnia.skrot``.
        kontekst["pierwszy_rok"] = pierwszy_rok
        kontekst["ostatni_rok"] = ostatni_rok
        return kontekst


def url_formularza_admina(rekord) -> str:
    """Adres formularza edycji rekordu w panelu administracyjnym.

    Nazwę trasy wyprowadzamy z metadanych modelu, zamiast trzymać słownik
    ``Osiagniecie → nazwa trasy``: raport dotyka trzech modeli
    (``Wydawnictwo_Ciagle``, ``Wydawnictwo_Zwarte``, ``Patent``), wszystkie
    zarejestrowane w adminie, a słownik byłby czwartym miejscem do
    zsynchronizowania przy każdej zmianie.
    """
    opcje = rekord._meta
    return reverse(
        f"admin:{opcje.app_label}_{opcje.model_name}_change", args=[rekord.pk]
    )
