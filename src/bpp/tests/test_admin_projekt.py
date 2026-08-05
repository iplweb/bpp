"""Testy adminów projektu badawczego, finansowania i instytucji finansujących."""

import pytest
from django.contrib import admin
from model_bakery import baker

from bpp.admin.grant import GrantAdmin
from bpp.admin.projekt import (
    FinansowanieInline,
    Instytucja_FinansujacaAdmin,
    Projekt_AutorInline,
    ProjektAdmin,
)
from bpp.admin.uczelnia import UczelniaAdmin
from bpp.models import Instytucja_Finansujaca, Projekt, Projekt_Autor

# Prefiks formsetu wyznaczony empirycznie przez ``get_default_prefix()``:
# ``BaseInlineFormSet`` bierze go z nazwy odwrotnego akcesora FK, a że
# ``Projekt_Autor.projekt`` nie ma ``related_name``, wychodzi
# ``projekt_autor_set``. Test ``test_prefiks_formsetu_sie_nie_zmienil``
# pilnuje, żeby pozostałe testy nie przechodziły przez przypadek na
# błędzie „ManagementForm data is missing".
PREFIKS = "projekt_autor_set"


def _formset_inline(rf, admin_user, projekt):
    inline = Projekt_AutorInline(Projekt, admin.site)
    request = rf.get("/")
    # ``get_formset`` pyta o uprawnienia (``can_delete``), więc request
    # bez ``user`` wywala się na AttributeError.
    request.user = admin_user
    return inline.get_formset(request, projekt)


def _dane(*wiersze):
    dane = {
        f"{PREFIKS}-TOTAL_FORMS": str(len(wiersze)),
        f"{PREFIKS}-INITIAL_FORMS": "0",
        f"{PREFIKS}-MIN_NUM_FORMS": "0",
        f"{PREFIKS}-MAX_NUM_FORMS": "1000",
    }
    for nr, (autor, rola) in enumerate(wiersze):
        dane[f"{PREFIKS}-{nr}-autor"] = str(autor.pk)
        dane[f"{PREFIKS}-{nr}-rola"] = rola
    return dane


@pytest.mark.django_db
def test_prefiks_formsetu_sie_nie_zmienil(rf, admin_user, jednostka):
    projekt = baker.make(Projekt, jednostka=jednostka)
    assert _formset_inline(rf, admin_user, projekt).get_default_prefix() == PREFIKS


@pytest.mark.django_db
def test_inline_odrzuca_dwoch_kierownikow(
    rf, admin_user, jednostka, autor_jan_nowak, autor_jan_kowalski
):
    projekt = baker.make(Projekt, jednostka=jednostka)
    FormSet = _formset_inline(rf, admin_user, projekt)
    formset = FormSet(
        _dane(
            (autor_jan_nowak, Projekt_Autor.ROLA_KIEROWNIK),
            (autor_jan_kowalski, Projekt_Autor.ROLA_KIEROWNIK),
        ),
        instance=projekt,
    )
    assert not formset.is_valid()
    # Asercja na treść błędu, nie na sam ``False`` -- inaczej test
    # przeszedłby również wtedy, gdyby formset odrzucił dane z powodu
    # rozjechanego prefiksu (brakujący ManagementForm).
    assert any("kierownika" in blad for blad in formset.non_form_errors())


@pytest.mark.django_db
def test_inline_przepuszcza_kierownika_i_wykonawce(
    rf, admin_user, jednostka, autor_jan_nowak, autor_jan_kowalski
):
    projekt = baker.make(Projekt, jednostka=jednostka)
    FormSet = _formset_inline(rf, admin_user, projekt)
    formset = FormSet(
        _dane(
            (autor_jan_nowak, Projekt_Autor.ROLA_KIEROWNIK),
            (autor_jan_kowalski, Projekt_Autor.ROLA_WYKONAWCA),
        ),
        instance=projekt,
    )
    assert formset.is_valid(), formset.errors


@pytest.mark.django_db
def test_inline_ignoruje_kierownika_skasowanego(
    rf, admin_user, jednostka, autor_jan_nowak, autor_jan_kowalski
):
    # Wiersz zaznaczony do skasowania nie może blokować nowego kierownika.
    projekt = baker.make(Projekt, jednostka=jednostka)
    Projekt_Autor.objects.create(
        projekt=projekt, autor=autor_jan_nowak, rola=Projekt_Autor.ROLA_KIEROWNIK
    )
    istniejacy = Projekt_Autor.objects.get(projekt=projekt)
    FormSet = _formset_inline(rf, admin_user, projekt)
    dane = {
        f"{PREFIKS}-TOTAL_FORMS": "2",
        f"{PREFIKS}-INITIAL_FORMS": "1",
        f"{PREFIKS}-MIN_NUM_FORMS": "0",
        f"{PREFIKS}-MAX_NUM_FORMS": "1000",
        f"{PREFIKS}-0-id": str(istniejacy.pk),
        f"{PREFIKS}-0-autor": str(autor_jan_nowak.pk),
        f"{PREFIKS}-0-rola": Projekt_Autor.ROLA_KIEROWNIK,
        f"{PREFIKS}-0-DELETE": "on",
        f"{PREFIKS}-1-autor": str(autor_jan_kowalski.pk),
        f"{PREFIKS}-1-rola": Projekt_Autor.ROLA_KIEROWNIK,
    }
    formset = FormSet(dane, instance=projekt)
    assert formset.is_valid(), formset.errors


@pytest.mark.django_db
def test_projekt_admin_ma_search_fields():
    # Bez ``search_fields`` autocomplete w innych adminach nie zadziała.
    assert ProjektAdmin.search_fields


def test_instytucja_finansujaca_admin_ma_search_fields():
    assert Instytucja_FinansujacaAdmin.search_fields


def test_projekt_i_instytucja_zarejestrowane_w_adminie():
    assert isinstance(admin.site._registry[Projekt], ProjektAdmin)
    assert isinstance(
        admin.site._registry[Instytucja_Finansujaca], Instytucja_FinansujacaAdmin
    )


def test_projekt_admin_ma_oba_inline():
    assert Projekt_AutorInline in ProjektAdmin.inlines
    assert FinansowanieInline in ProjektAdmin.inlines


def test_grant_admin_pokazuje_i_wyszukuje_projekt():
    assert "projekt" in GrantAdmin.list_display
    assert "projekt" in GrantAdmin.autocomplete_fields


def test_uczelnia_admin_ma_przelacznik_kwot():
    # Przełącznik musi siedzieć w tym samym fieldsecie, co reszta ustawień
    # eksportu CERIF -- inaczej redaktor go nie znajdzie.
    for _nazwa, opcje in UczelniaAdmin.fieldsets:
        pola = opcje["fields"]
        if "eksport_cerif_osoby" in pola:
            assert "eksport_cerif_kwoty" in pola
            break
    else:
        pytest.fail("Nie znaleziono fieldsetu z ustawieniami eksportu CERIF")
