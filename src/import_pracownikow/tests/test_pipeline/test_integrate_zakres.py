"""Integracja importu pracowników — rozgałęzienie wg ``zakres_integracji``:

- ``ZAKRES_JEDNOSTKI``: tworzy TYLKO jednostki (bez tytułów, bez osób),
- ``ZAKRES_STRUKTURA``: tworzy jednostki + tytuły (bez osób),
- ``ZAKRES_PELNY``: pełny przebieg (struktura + osoby) — regresja.

Wspólny motyw: dla zakresów strukturalnych osoby MUSZĄ pozostać nietknięte
(zero zapisów ``Autor`` / ``Autor_Jednostka``), mimo że wiersz miałby w pełnym
imporcie utworzyć nowego autora."""

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka, Tytul
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowJednostka,
    ImportPracownikowRow,
    ImportPracownikowTytul,
)
from import_pracownikow.pewnosc import STATUS_BRAK
from import_pracownikow.pipeline.integrate import integruj
from import_pracownikow.tests._helpers import unikalna_nazwa


def _imp(zakres):
    return baker.make(
        ImportPracownikow,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
        zakres_integracji=zakres,
    )


def _decyzja_jednostki(imp):
    # Nazwa unikalna: integracja materializuje ją jako Jednostkę (unikalne
    # nazwa/skrot/slug), a testy w tym pliku dzielą ten helper — pod ambient
    # pollution xdista dosłowna "Zakład Struktury Testowej" kolidowałaby między
    # sąsiadami. Asercje odwołują się do ``dec_j.nazwa_zrodlowa``.
    return baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        nazwa_zrodlowa=unikalna_nazwa("Zakład Struktury Testowej"),
        skrot_sugerowany="ZST",
        tryb=ImportPracownikowJednostka.TRYB_BRAK,
        decyzja=ImportPracownikowJednostka.DECYZJA_AKCEPTUJ,
    )


def _decyzja_tytulu(imp):
    nazwa = unikalna_nazwa("Tytuł Struktury Testowej")
    return baker.make(
        ImportPracownikowTytul,
        parent=imp,
        nazwa_zrodlowa=nazwa,
        nazwa_do_utworzenia=nazwa,
        skrot_do_utworzenia="TytStrTest",
        tryb=ImportPracownikowTytul.TRYB_BRAK,
        decyzja=ImportPracownikowTytul.DECYZJA_AKCEPTUJ,
    )


def _wiersz_nowy_autor(imp, dec_j, dec_t=None):
    """Wiersz, który w PEŁNYM imporcie utworzyłby nowego Autora + Autor_Jednostka
    (``confidence=brak`` + ``utworz_nowego`` + jednostka do rozstrzygnięcia)."""
    return ImportPracownikowRow.objects.create(
        parent=imp,
        autor=None,
        jednostka=None,
        zrodlo_jednostki=dec_j,
        zrodlo_tytulu=dec_t,
        jednostka_status=dec_j.tryb,
        tytul_status=dec_t.tryb if dec_t is not None else None,
        confidence=STATUS_BRAK,
        utworz_nowego=True,
        dane_znormalizowane={"nazwisko": "Strukturalny", "imię": "Jan"},
        diff_do_utworzenia={},
        zmiany_potrzebne=False,
    )


@pytest.mark.django_db
def test_zakres_jednostki_tworzy_jednostki_bez_tytulow_bez_osob(uczelnia):
    imp = _imp(ImportPracownikow.ZAKRES_JEDNOSTKI)
    dec_j = _decyzja_jednostki(imp)
    dec_t = _decyzja_tytulu(imp)
    row = _wiersz_nowy_autor(imp, dec_j, dec_t)
    autorow_przed = Autor.objects.count()
    aj_przed = Autor_Jednostka.objects.count()

    p = MockProgress(imp)
    integruj(imp, p)

    imp.refresh_from_db()
    # Krok 1: struktura zapisana, osoby czekają (NIE „zintegrowany").
    assert imp.stan == ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA
    # jednostki utworzone
    dec_j.refresh_from_db()
    assert dec_j.utworzona is not None
    assert Jednostka.objects.filter(nazwa=dec_j.nazwa_zrodlowa).exists()
    # tytuły POMINIĘTE (zakres tylko jednostki)
    dec_t.refresh_from_db()
    assert dec_t.utworzony is None
    assert not Tytul.objects.filter(nazwa=dec_t.nazwa_do_utworzenia).exists()
    # osoby NIETKNIĘTE — brak zapisów Autor / Autor_Jednostka
    assert Autor.objects.count() == autorow_przed
    assert Autor_Jednostka.objects.count() == aj_przed
    row.refresh_from_db()
    assert row.autor_id is None
    # panel wyniku: flaga zakresu + liczniki struktury
    assert p.result_context["zakres"] == ImportPracownikow.ZAKRES_JEDNOSTKI
    assert p.result_context["utworzono_jednostek"] == 1
    assert p.result_context["utworzono_tytulow"] == 0


@pytest.mark.django_db
def test_zakres_struktura_tworzy_jednostki_i_tytuly_bez_osob(uczelnia):
    imp = _imp(ImportPracownikow.ZAKRES_STRUKTURA)
    dec_j = _decyzja_jednostki(imp)
    dec_t = _decyzja_tytulu(imp)
    row = _wiersz_nowy_autor(imp, dec_j, dec_t)
    autorow_przed = Autor.objects.count()
    aj_przed = Autor_Jednostka.objects.count()

    p = MockProgress(imp)
    integruj(imp, p)

    imp.refresh_from_db()
    # Krok 1: struktura zapisana, osoby czekają (NIE „zintegrowany").
    assert imp.stan == ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA
    # jednostki + tytuły utworzone
    assert Jednostka.objects.filter(nazwa=dec_j.nazwa_zrodlowa).exists()
    dec_t.refresh_from_db()
    assert dec_t.utworzony is not None
    assert Tytul.objects.filter(nazwa=dec_t.nazwa_do_utworzenia).exists()
    # osoby NIETKNIĘTE
    assert Autor.objects.count() == autorow_przed
    assert Autor_Jednostka.objects.count() == aj_przed
    row.refresh_from_db()
    assert row.autor_id is None
    assert p.result_context["zakres"] == ImportPracownikow.ZAKRES_STRUKTURA
    assert p.result_context["utworzono_jednostek"] == 1
    assert p.result_context["utworzono_tytulow"] == 1


@pytest.mark.django_db
def test_zakres_pelny_tworzy_osoby(uczelnia):
    """Regresja rozgałęzienia: ``ZAKRES_PELNY`` przechodzi pełną ścieżkę i
    faktycznie tworzy nowego autora + powiązanie (przeciwieństwo zakresów
    strukturalnych)."""
    imp = _imp(ImportPracownikow.ZAKRES_PELNY)
    dec_j = _decyzja_jednostki(imp)
    row = _wiersz_nowy_autor(imp, dec_j)
    autorow_przed = Autor.objects.count()
    aj_przed = Autor_Jednostka.objects.count()

    p = MockProgress(imp)
    integruj(imp, p)

    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY
    row.refresh_from_db()
    assert row.autor_id is not None  # nowy autor utworzony w pełnym imporcie
    assert Autor.objects.count() == autorow_przed + 1
    assert Autor_Jednostka.objects.count() == aj_przed + 1
    # pełny przebieg nie ustawia klucza `zakres` w result_context
    assert "zakres" not in p.result_context
    assert p.result_context["utworzono_nowych_autorow"] == 1


@pytest.mark.django_db
def test_sekwencja_jednostki_potem_pelny_tworzy_odlozony_tytul(uczelnia):
    """Uwaga reviewera #2 (decyzja: ODROCZENIE): tytuł świadomie pominięty w
    Kroku 1 („tylko jednostki") zostaje UTWORZONY w Kroku 2 (import osób =
    pełny). Import osób i tak wymaga tytułów, więc to zachowanie jest zamierzone
    — dokumentujemy sekwencję ``jednostki → pelny`` z nierozstrzygniętym tytułem,
    której brakowało w testach."""
    imp = _imp(ImportPracownikow.ZAKRES_JEDNOSTKI)
    dec_j = _decyzja_jednostki(imp)
    dec_t = _decyzja_tytulu(imp)
    _wiersz_nowy_autor(imp, dec_j, dec_t)

    # Krok 1 — tylko jednostki: tytuł ODROCZONY (nie utworzony).
    integruj(imp, MockProgress(imp))
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA
    dec_t.refresh_from_db()
    assert dec_t.utworzony is None
    assert not Tytul.objects.filter(nazwa=dec_t.nazwa_do_utworzenia).exists()

    # Krok 2 — import osób (pełny): odłożony tytuł zostaje utworzony.
    imp.stan = ImportPracownikow.STAN_ZATWIERDZONY
    imp.zakres_integracji = ImportPracownikow.ZAKRES_PELNY
    imp.save(update_fields=["stan", "zakres_integracji"])
    integruj(imp, MockProgress(imp))
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY
    dec_t.refresh_from_db()
    assert dec_t.utworzony is not None
    assert Tytul.objects.filter(nazwa=dec_t.nazwa_do_utworzenia).exists()


@pytest.mark.django_db
def test_on_restart_resetuje_zakres_do_pelny():
    """Po strukturalnym imporcie ponowna analiza (cofnięcie do zmapowany)
    wraca do pełnego zakresu — inaczej kolejne „Zapisz do bazy" pominęłoby
    osoby."""
    imp = baker.make(
        ImportPracownikow,
        stan=ImportPracownikow.STAN_ZMAPOWANY,
        zakres_integracji=ImportPracownikow.ZAKRES_STRUKTURA,
    )
    imp.on_restart()
    imp.refresh_from_db()
    assert imp.zakres_integracji == ImportPracownikow.ZAKRES_PELNY
