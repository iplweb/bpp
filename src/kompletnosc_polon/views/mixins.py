"""Wspólne mixiny widoków raportu kompletności danych POL-on."""

from django.urls import reverse
from django.utils.functional import cached_property

from ewaluacja_common.const import OKNO_EWALUACJI
from ewaluacja_metryki.views.mixins import (
    EwaluacjaRequiredMixin,
    ma_pelne_uprawnienia_ewaluacji,
)
from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu


def opis_okna(okno: tuple[int, int | None]) -> str:
    """Zakres lat okna raportu tak, jak ma go zobaczyć użytkownik.

    Dwa warianty, bo :data:`ewaluacja_common.const.OKNO_EWALUACJI` ma dziś
    górną granicę nieustaloną:

    * okno domknięte → ``"2026–2029"`` (półpauza, jak w typografii zakresu);
    * okno otwarte (``ostatni_rok`` to ``None``) → ``"od 2026"``.

    Wariant otwarty musi mieć własne zdanie, a nie sklejkę z pustym miejscem:
    „2026–None” byłoby wyciekiem implementacji, a „2026–” — sugestią, że
    czegoś w szablonie brakuje. „Od 2026” jest po prostu prawdą.

    Zwracamy półpauzę jako znak (U+2013), nie encję ``&ndash;``: encja
    w automatycznie escape'owanym szablonie wyszłaby jako dosłowne
    „&amp;ndash;”, a znak renderuje się tak samo i nie wymaga ``mark_safe``.
    """
    pierwszy_rok, ostatni_rok = okno
    if ostatni_rok is None:
        return f"od {pierwszy_rok}"
    return f"{pierwszy_rok}–{ostatni_rok}"


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

    okno: tuple[int, int | None] = OKNO_EWALUACJI

    @cached_property
    def uczelnia(self):
        return uczelnia_dla_odczytu(self.request)

    def get_context_data(self, **kwargs):
        kontekst = super().get_context_data(**kwargs)
        # Świadomie NIE wystawiamy tu ``uczelnia`` — pod tą nazwą base.html
        # dostaje uczelnię z context processora i nadpisanie jej wartością
        # ``None`` (instalacja bez mapowania Site→Uczelnia) wywala szablon
        # bazowy przy ``uczelnia.skrot``.
        #
        # Do szablonu idzie GOTOWY opis zakresu, a nie para liczb: przy
        # otwartej górnej granicy ``ostatni_rok`` jest ``None`` i każde
        # sklejanie „{{ pierwszy_rok }}–{{ ostatni_rok }}” w szablonie
        # wyrenderowałoby „2026–None”. Jedno miejsce decyduje o brzmieniu
        # zakresu — patrz :func:`opis_okna`.
        kontekst["zakres_lat"] = opis_okna(self.okno)
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
