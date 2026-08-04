"""Testy słowników kontrolowanych i raportu mapowań.

Funkcje w ``cerif_export.slowniki`` mają być **czyste** — dostają obiekt
pobrany wcześniej przez provider albo ``None`` i nie dotykają bazy. Dlatego
większość testów posługuje się zwykłymi atrapami (``SimpleNamespace``):
gdyby któraś funkcja spróbowała czegokolwiek z ORM-a, test padnie na
``AttributeError`` zamiast po cichu przejść.
"""

import io
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from model_bakery import baker

from bpp.models import (
    Charakter_Formalny,
    Jezyk,
    Licencja_OpenAccess,
    Rodzaj_Prawa_Patentowego,
    Tryb_OpenAccess_Wydawnictwo_Ciagle,
    Tryb_OpenAccess_Wydawnictwo_Zwarte,
)
from cerif_export.slowniki import coar, dostep, jezyki, licencje

JOURNAL_ARTICLE = coar.BAZA + "c_6501"
UTILITY_MODEL = coar.BAZA + "9DKX-KSAF"
SPOZA_SLOWNIKA = "http://example.invalid/typ"


def test_coar_slowniki_zawieraja_korzenie_galezi():
    assert coar.TEKST_ROOT in coar.TYPY_TEKSTOWE
    assert coar.PATENT_ROOT in coar.TYPY_PATENTOWE
    assert coar.JOURNAL in coar.TYPY_TEKSTOWE
    assert coar.DOCTORAL_THESIS in coar.TYPY_TEKSTOWE
    assert coar.THESIS in coar.TYPY_TEKSTOWE


def test_coar_galezie_sa_rozlaczne():
    # Profil ogranicza Publication/Type i Patent/Type do dwóch osobnych
    # enumeracji; wspólny termin oznaczałby błąd przepisania słownika.
    assert not set(coar.TYPY_TEKSTOWE) & set(coar.TYPY_PATENTOWE)


def test_coar_slowniki_maja_komplet_terminow():
    # Liczności wg plików schematu profilu 1.2 (coar_publication_types.xsd
    # oraz coar_patent_types.xsd) — kotwica na wypadek gubienia wierszy.
    assert len(coar.TYPY_TEKSTOWE) == 58
    assert len(coar.TYPY_PATENTOWE) == 7
    assert len(coar.WSZYSTKIE) == 65


def test_coar_wszystkie_uri_maja_wspolny_prefiks():
    for uri in coar.WSZYSTKIE:
        assert uri.startswith(coar.BAZA)


@pytest.mark.parametrize(
    "wejscie",
    [None, "", "   ", SPOZA_SLOWNIKA, coar.PATENT_ROOT, UTILITY_MODEL],
)
def test_typ_publikacji_fallback(wejscie):
    # Także URI z gałęzi patentowej jest tu wartością nieprawidłową —
    # przepuszczony wprost wywaliłby walidację XSD.
    assert coar.typ_publikacji(wejscie) == coar.TEKST_ROOT


@pytest.mark.parametrize("wejscie", [JOURNAL_ARTICLE, coar.THESIS, coar.JOURNAL])
def test_typ_publikacji_zwraca_znana_wartosc(wejscie):
    assert coar.typ_publikacji(wejscie) == wejscie


def test_typ_publikacji_obcina_biale_znaki():
    assert coar.typ_publikacji(f"  {JOURNAL_ARTICLE}\n") == JOURNAL_ARTICLE


@pytest.mark.parametrize(
    "wejscie",
    [None, "", "   ", SPOZA_SLOWNIKA, coar.TEKST_ROOT, JOURNAL_ARTICLE],
)
def test_typ_patentu_fallback(wejscie):
    assert coar.typ_patentu(wejscie) == coar.PATENT_ROOT


@pytest.mark.parametrize("wejscie", [UTILITY_MODEL, coar.PATENT_ROOT])
def test_typ_patentu_zwraca_znana_wartosc(wejscie):
    assert coar.typ_patentu(wejscie) == wejscie


def test_typ_patentu_obcina_biale_znaki():
    assert coar.typ_patentu(f" {UTILITY_MODEL} ") == UTILITY_MODEL


@pytest.mark.parametrize(
    "uri",
    [
        coar.TEKST_ROOT,
        coar.PATENT_ROOT,
        coar.JOURNAL,
        coar.DOCTORAL_THESIS,
        coar.THESIS,
        JOURNAL_ARTICLE,
        UTILITY_MODEL,
        f"  {JOURNAL_ARTICLE}  ",
    ],
)
def test_znany_akceptuje_slownikowe(uri):
    assert coar.znany(uri) is True


@pytest.mark.parametrize(
    "uri",
    [
        None,
        "",
        "   ",
        SPOZA_SLOWNIKA,
        "c_6501",
        coar.BAZA + "c_6501x",
        coar.BAZA,
    ],
)
def test_znany_odrzuca_pozostale(uri):
    assert coar.znany(uri) is False


def test_prawo_dostepu_none():
    assert dostep.prawo_dostepu(None) is None


@pytest.mark.parametrize("uri", dostep.WSZYSTKIE)
def test_prawo_dostepu_zwraca_znane_uri(uri):
    assert dostep.prawo_dostepu(SimpleNamespace(coar_access_right=uri)) == uri


@pytest.mark.parametrize(
    "wartosc",
    ["", "   ", None, SPOZA_SLOWNIKA, coar.TEKST_ROOT],
)
def test_prawo_dostepu_brak_mapowania(wartosc):
    tryb = SimpleNamespace(coar_access_right=wartosc)
    assert dostep.prawo_dostepu(tryb) is None


def test_prawo_dostepu_obcina_biale_znaki():
    tryb = SimpleNamespace(coar_access_right=f"\t{dostep.OPEN} ")
    assert dostep.prawo_dostepu(tryb) == dostep.OPEN


def test_uri_licencji_none():
    assert licencje.uri_licencji(None) is None


@pytest.mark.parametrize("wartosc", ["", "   ", None])
def test_uri_licencji_brak_wartosci(wartosc):
    assert licencje.uri_licencji(SimpleNamespace(uri=wartosc)) is None


def test_uri_licencji_zwraca_wartosc():
    uri = "https://creativecommons.org/licenses/by/4.0/"
    assert licencje.uri_licencji(SimpleNamespace(uri=f"  {uri}  ")) == uri


def test_kod_jezyka_none():
    assert jezyki.kod_jezyka(None) is None


@pytest.mark.parametrize("wartosc", ["", "   ", None])
def test_kod_jezyka_brak_wartosci(wartosc):
    assert jezyki.kod_jezyka(SimpleNamespace(kod_bcp47=wartosc)) is None


def test_kod_jezyka_zwraca_wartosc():
    assert jezyki.kod_jezyka(SimpleNamespace(kod_bcp47=" en-GB ")) == "en-GB"


@pytest.mark.django_db
def test_slowniki_nie_odpytuja_bazy(django_assert_num_queries):
    """Na realnych obiektach ORM też ani jednego zapytania.

    Provider dostarcza obiekty gotowe; lazy-load w serializerze zamieniłby
    pełny harvest w N+1 przy setkach tysięcy rekordów.
    """
    jezyk = baker.make(Jezyk, kod_bcp47="pl")
    licencja = baker.make(
        Licencja_OpenAccess, uri="https://creativecommons.org/licenses/by/4.0/"
    )
    tryb = baker.make(Tryb_OpenAccess_Wydawnictwo_Ciagle, coar_access_right=dostep.OPEN)
    charakter = baker.make(Charakter_Formalny, coar_type=JOURNAL_ARTICLE)

    with django_assert_num_queries(0):
        assert jezyki.kod_jezyka(jezyk) == "pl"
        assert licencje.uri_licencji(licencja) is not None
        assert dostep.prawo_dostepu(tryb) == dostep.OPEN
        assert coar.typ_publikacji(charakter.coar_type) == JOURNAL_ARTICLE


def _uruchom_raport():
    stdout = io.StringIO()
    call_command("cerif_raport_mapowan", stdout=stdout)
    return stdout.getvalue()


@pytest.mark.django_db
def test_raport_mapowan_na_pustych_slownikach():
    """Komenda nie wywala się, gdy nie ma czego raportować."""
    for model in (
        Charakter_Formalny,
        Rodzaj_Prawa_Patentowego,
        Jezyk,
        Licencja_OpenAccess,
        Tryb_OpenAccess_Wydawnictwo_Ciagle,
        Tryb_OpenAccess_Wydawnictwo_Zwarte,
    ):
        model.objects.all().delete()

    wynik = _uruchom_raport()

    assert "Raport mapowań" in wynik
    assert "RAZEM pozycji wymagających uwagi redakcji: 0" in wynik
    assert "Wszystkie wartości słownikowe są uzupełnione." in wynik


@pytest.mark.django_db
def test_raport_mapowan_charakter_formalny_bez_coar_type():
    baker.make(
        Charakter_Formalny,
        nazwa="Charakter Bez Mapowania",
        skrot="CBM1",
        coar_type="",
    )

    wynik = _uruchom_raport()

    assert "Charakter Bez Mapowania [CBM1] — brak wartości" in wynik
    assert "Charaktery formalne bez poprawnego typu COAR" in wynik


@pytest.mark.django_db
def test_raport_mapowan_charakter_formalny_spoza_slownika():
    baker.make(
        Charakter_Formalny,
        nazwa="Charakter Ze Smieciem",
        skrot="CZS1",
        coar_type=SPOZA_SLOWNIKA,
    )

    wynik = _uruchom_raport()

    assert (
        f"Charakter Ze Smieciem [CZS1] — wartość spoza słownika COAR: {SPOZA_SLOWNIKA}"
    ) in wynik


@pytest.mark.django_db
def test_raport_mapowan_charakter_formalny_z_galezi_patentowej():
    # URI patentu przy charakterze formalnym to wartość z niewłaściwej
    # enumeracji — eksport i tak podstawi korzeń, więc raport musi to widzieć.
    baker.make(
        Charakter_Formalny,
        nazwa="Charakter Z Patentem",
        skrot="CZP1",
        coar_type=UTILITY_MODEL,
    )

    wynik = _uruchom_raport()

    assert "Charakter Z Patentem [CZP1] — wartość spoza słownika COAR" in wynik


@pytest.mark.django_db
def test_raport_mapowan_charakter_formalny_zmapowany_nie_wychodzi():
    baker.make(
        Charakter_Formalny,
        nazwa="Charakter Zmapowany",
        skrot="CZM1",
        coar_type=JOURNAL_ARTICLE,
    )

    assert "Charakter Zmapowany" not in _uruchom_raport()


@pytest.mark.django_db
def test_raport_mapowan_rodzaj_prawa_patentowego_po_nazwie():
    """``Rodzaj_Prawa_Patentowego`` nie ma pola ``skrot``."""
    baker.make(Rodzaj_Prawa_Patentowego, nazwa="Prawo Bez Mapowania", coar_type="")

    wynik = _uruchom_raport()

    assert "Prawo Bez Mapowania — brak wartości" in wynik
    assert "Rodzaje praw patentowych bez poprawnego typu COAR" in wynik


@pytest.mark.django_db
def test_raport_mapowan_jezyk_bez_kodu():
    baker.make(Jezyk, nazwa="jezyk testowy", skrot="tst.", kod_bcp47="")

    wynik = _uruchom_raport()

    assert "jezyk testowy [tst.]" in wynik
    assert "Języki bez kodu BCP 47" in wynik


@pytest.mark.django_db
def test_raport_mapowan_licencja_bez_uri():
    # Skróty licencji z baseline'u (CC-BY, OTHER, ...) są zajęte, stąd
    # własne, jawnie testowe wartości.
    baker.make(
        Licencja_OpenAccess, nazwa="Licencja Testowa Inna", skrot="TEST-OTHER", uri=""
    )

    wynik = _uruchom_raport()

    assert "Licencja Testowa Inna [TEST-OTHER]" in wynik
    assert "Licencje Open Access bez adresu URI" in wynik


@pytest.mark.django_db
def test_raport_mapowan_licencja_z_uri_wygenerowanym_automatycznie():
    baker.make(
        Licencja_OpenAccess,
        nazwa="Licencja Testowa CC BY",
        skrot="CC-TEST-BY",
        uri="https://creativecommons.org/licenses/test-by/4.0/",
    )

    wynik = _uruchom_raport()

    assert "wymagają potwierdzenia" in wynik
    assert "Licencja Testowa CC BY [CC-TEST-BY]" in wynik
    assert "adresy licencji do potwierdzenia: " in wynik


@pytest.mark.django_db
def test_raport_mapowan_licencja_z_uri_od_redakcji():
    """Adres z inną wersją niż domyślana przez migrację jest decyzją
    redakcji — nie ma po co go potwierdzać drugi raz."""
    baker.make(
        Licencja_OpenAccess,
        nazwa="Licencja Testowa CC BY SA",
        skrot="CC-TEST-SA",
        uri="https://creativecommons.org/licenses/test-sa/3.0/",
    )

    assert "Licencja Testowa CC BY SA" not in _uruchom_raport()


@pytest.mark.django_db
def test_raport_mapowan_cc0_nie_wymaga_potwierdzenia():
    """CC0 ma jedną wersję (1.0), więc jej URI jest dokładny."""
    baker.make(
        Licencja_OpenAccess,
        nazwa="Licencja Testowa CC ZERO",
        skrot="CC-0",
        uri="https://creativecommons.org/publicdomain/zero/1.0/",
    )

    assert "Licencja Testowa CC ZERO" not in _uruchom_raport()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model,naglowek",
    [
        (
            Tryb_OpenAccess_Wydawnictwo_Ciagle,
            "Tryby Open Access wyd. ciągłych bez prawa dostępu COAR",
        ),
        (
            Tryb_OpenAccess_Wydawnictwo_Zwarte,
            "Tryby Open Access wyd. zwartych bez prawa dostępu COAR",
        ),
    ],
)
def test_raport_mapowan_tryby_openaccess(model, naglowek):
    baker.make(model, nazwa="Tryb Bez Mapowania", skrot="TBM1", coar_access_right="")

    wynik = _uruchom_raport()

    assert naglowek in wynik
    assert "Tryb Bez Mapowania [TBM1] — brak wartości" in wynik


@pytest.mark.django_db
def test_raport_mapowan_tryb_openaccess_spoza_slownika():
    baker.make(
        Tryb_OpenAccess_Wydawnictwo_Zwarte,
        nazwa="Tryb Ze Smieciem",
        skrot="TZS1",
        coar_access_right=SPOZA_SLOWNIKA,
    )

    assert "wartość spoza słownika COAR Access Rights" in _uruchom_raport()


@pytest.mark.django_db
def test_raport_mapowan_liczy_podsumowanie():
    baker.make(Charakter_Formalny, nazwa="Charakter Do Policzenia", coar_type="")

    wynik = _uruchom_raport()

    assert "Podsumowanie" in wynik
    assert "charaktery formalne " in wynik
    # Suma nie może być zerowa, skoro co najmniej jeden wiersz jest bez
    # mapowania.
    assert "RAZEM pozycji wymagających uwagi redakcji: 0" not in wynik
