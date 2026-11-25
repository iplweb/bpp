"""Porównanie pól w komparatorze publikacji PBN (FD#517).

Komparator porównuje pola tym samym silnikiem co „Wzbogać z PBN”
(``importer_publikacji.wzbogacanie.pola``) — jedna reguła porównywania.
Przy każdym polu, którego wynik zmienił się względem wcześniejszego
komparatora, komentarz „BYŁO → JEST” mówi, co się zmieniło.

Pola spoza silnika (liczba autorów, wydawca, konferencja, miejsce wydania,
seria, punkty) są porównywane jak dotąd — ich testy przypinają stan zastany.
"""

import pytest
from model_bakery import baker

from bpp.models import Jezyk
from komparator_publikacji_pbn.views import (
    COMPARISON_FIELDS,
    PublicationComparisonView,
)
from pbn_api.models import Publication

pytestmark = pytest.mark.django_db

WSZYSTKIE_POLA = list(COMPARISON_FIELDS)


def _pbn(**obiekt):
    return Publication.objects.create(
        mongoId=baker.random_gen.gen_string(24),
        status="ACTIVE",
        versions=[{"current": True, "object": obiekt}],
    )


def _roznice(rekord, rodzaj, pola=None):
    wynik = PublicationComparisonView()._compare_publication(
        rekord, rodzaj, pola or WSZYSTKIE_POLA
    )
    return {r["field"]: (r["bpp_value"], r["pbn_value"]) for r in wynik["differences"]}


def _ciagle(wydawnictwo_ciagle, pbn, **pola):
    w = wydawnictwo_ciagle
    w.pbn_uid = pbn
    w.jezyk = Jezyk.objects.get(skrot="pol.")
    w.punkty_kbn = 0
    w.public_www = ""
    w.www = ""
    w.issn = ""
    w.e_issn = ""
    w.tom = ""
    w.nr_zeszytu = ""
    w.strony = ""
    w.doi = None
    for nazwa, wartosc in pola.items():
        setattr(w, nazwa, wartosc)
    w.save()
    return w


def _zwarte(wydawnictwo_zwarte, pbn, **pola):
    w = wydawnictwo_zwarte
    w.pbn_uid = pbn
    w.jezyk = Jezyk.objects.get(skrot="pol.")
    w.punkty_kbn = 0
    w.public_www = ""
    w.www = ""
    w.tom = ""
    w.strony = ""
    w.isbn = ""
    w.e_isbn = ""
    w.issn = ""
    w.e_issn = ""
    w.doi = None
    w.miejsce_i_rok = ""
    w.wydawca = None
    w.wydawca_opis = ""
    for nazwa, wartosc in pola.items():
        setattr(w, nazwa, wartosc)
    w.save()
    return w


def _zgodny_obiekt(rekord, **nadpisz):
    obiekt = {
        "title": rekord.tytul_oryginalny,
        "year": rekord.rok,
        "mainLanguage": "pol",
    }
    obiekt.update(nadpisz)
    return obiekt


def _ustaw(pbn, rekord, **nadpisz):
    pbn.versions = [{"current": True, "object": _zgodny_obiekt(rekord, **nadpisz)}]
    pbn.save()
    return Publication.objects.get(pk=pbn.pk)


@pytest.fixture
def para_ciagle(wydawnictwo_ciagle):
    """(rekord, funkcja ustawiająca obiekt PBN) — domyślnie bez różnic."""
    pbn = _pbn()
    rekord = _ciagle(wydawnictwo_ciagle, pbn)

    def ustaw(**nadpisz):
        rekord.pbn_uid = _ustaw(pbn, rekord, **nadpisz)
        return rekord

    return rekord, ustaw


@pytest.fixture
def para_zwarte(wydawnictwo_zwarte):
    pbn = _pbn()
    rekord = _zwarte(wydawnictwo_zwarte, pbn)

    def ustaw(**nadpisz):
        rekord.pbn_uid = _ustaw(pbn, rekord, **nadpisz)
        return rekord

    return rekord, ustaw


def test_brak_roznic(para_ciagle, para_zwarte):
    rekord, ustaw = para_ciagle
    assert _roznice(ustaw(), "ciagle") == {}
    rekord, ustaw = para_zwarte
    assert _roznice(ustaw(), "zwarte") == {}


def test_wynik_ma_dotychczasowy_ksztalt(para_ciagle):
    """Kształt wyniku się nie zmienił — korzysta z niego widok, eksport XLSX
    i przeliczanie w tle (FD#514)."""
    rekord, ustaw = para_ciagle
    wynik = PublicationComparisonView()._compare_publication(
        ustaw(title="Inny"), "ciagle", ["title"]
    )
    assert wynik["has_differences"] is True
    assert wynik["type"] == "ciagle"
    assert wynik["bpp_id"] == rekord.pk
    assert wynik["pbn_id"] == rekord.pbn_uid_id
    assert wynik["bpp_publication"] is rekord
    assert wynik["differences"] == [
        {"field": "Tytuł", "bpp_value": rekord.tytul_oryginalny, "pbn_value": "Inny"}
    ]


@pytest.mark.parametrize(
    "bpp,pbn,rozni_sie",
    [
        ("Tytuł pracy", "Tytuł pracy", False),
        ("<i>Tytuł</i> pracy", "Tytuł pracy", False),
        ("  Tytuł pracy ", " Tytuł pracy  ", False),
        ("Tytuł Pracy", "Tytuł pracy", True),
        ("Tytuł pracy", "Inny tytuł", True),
        # BYŁO: różnica (znaczniki usuwano tylko po stronie BPP).
        # JEST: zgodne — znaczniki HTML nie mają znaczenia po żadnej stronie.
        ("Tytuł pracy", "<i>Tytuł</i> pracy", False),
        # BYŁO: różnica. JEST: zgodne — podwójny odstęp to nie inny tytuł.
        ("Tytuł  pracy", "Tytuł pracy", False),
    ],
)
def test_tytul(para_ciagle, bpp, pbn, rozni_sie):
    rekord, ustaw = para_ciagle
    rekord.tytul_oryginalny = bpp
    assert ("Tytuł" in _roznice(ustaw(title=pbn), "ciagle")) is rozni_sie


def test_dlugie_wartosci_sa_skracane(para_ciagle):
    """BYŁO: tytuł skracany do 100 znaków (różnica dalej była niewidoczna).
    JEST: wartości do 300 znaków w całości, dłuższe skrócone."""
    rekord, ustaw = para_ciagle
    rekord.tytul_oryginalny = "A" * 150
    roznice = _roznice(ustaw(title="B" * 400), "ciagle")
    assert roznice["Tytuł"] == ("A" * 150, "B" * 300 + "...")


@pytest.mark.parametrize(
    "bpp,pbn,oczekiwane",
    [
        (2023, 2023, None),
        (2023, 2024, ("2023", "2024")),
        (2023, "2023", None),
        # BYŁO: brak roku w PBN nie był zgłaszany. JEST: jest różnicą.
        (2023, None, ("2023", "")),
    ],
)
def test_rok(para_ciagle, bpp, pbn, oczekiwane):
    rekord, ustaw = para_ciagle
    rekord.rok = bpp
    assert _roznice(ustaw(year=pbn), "ciagle").get("Rok") == oczekiwane


def test_rok_rozdzialu_z_ksiazki(para_zwarte):
    """Rok rozdziału PBN podaje przy książce — jak dotąd nie jest to brak."""
    rekord, ustaw = para_zwarte
    rekord = ustaw(year=None, book={"year": rekord.rok})
    assert "Rok" not in _roznice(rekord, "zwarte")


@pytest.mark.parametrize(
    "bpp,pbn,rozni_sie",
    [
        ("10.1/abc", "10.1/abc", False),
        ("10.1/ABC", " 10.1/abc ", False),
        (None, "", False),
        (None, "10.1/abc", True),
        ("10.1/abc", "", True),
        ("10.1/abc", "10.1/xyz", True),
        # BYŁO: różnica (adres zamiast numeru był „innym” DOI).
        # JEST: zgodne — liczy się sam numer DOI.
        ("10.1/abc", "https://doi.org/10.1/abc", False),
    ],
)
def test_doi(para_ciagle, bpp, pbn, rozni_sie):
    rekord, ustaw = para_ciagle
    rekord.doi = bpp
    assert ("DOI" in _roznice(ustaw(doi=pbn), "ciagle")) is rozni_sie


@pytest.mark.parametrize(
    "isbn,e_isbn,pbn,rozni_sie",
    [
        ("978-83-01-00000-1", "", "9788301000001", False),
        ("", "", "", False),
        # ISBN z PBN zapisany w BPP jako e-ISBN — zgodne, jak dotąd.
        ("", "978-83-01-00000-1", "9788301000001", False),
        ("978-83-01-00000-1", "", "978-83-01-00000-2", True),
        ("", "", "9788301000001", True),
        ("978-83-01-00000-1", "", "", True),
        # BYŁO: różnica. JEST: zgodne — znak kontrolny „X” bez rozróżniania
        # wielkości liter.
        ("83-01-00000-x", "", "83-01-00000-X", False),
    ],
)
def test_isbn_ksiazki(para_zwarte, isbn, e_isbn, pbn, rozni_sie):
    rekord, ustaw = para_zwarte
    rekord.isbn, rekord.e_isbn = isbn, e_isbn
    assert ("ISBN" in _roznice(ustaw(isbn=pbn), "zwarte", ["isbn"])) is rozni_sie


def test_e_isbn_tylko_w_bpp_jest_zglaszany(para_zwarte):
    """BYŁO: e-ISBN wpisany tylko w BPP nie był zgłaszany.
    JEST: osobna różnica „e-ISBN” (PBN go nie ma)."""
    rekord, ustaw = para_zwarte
    rekord.isbn, rekord.e_isbn = "978-83-01-00000-1", "978-83-01-00000-8"
    roznice = _roznice(ustaw(isbn="9788301000001"), "zwarte", ["isbn"])
    assert roznice == {"e-ISBN": ("978-83-01-00000-8", "")}


def test_isbn_nie_dotyczy_wydawnictw_ciaglych(para_ciagle):
    rekord, ustaw = para_ciagle
    assert "ISBN" not in _roznice(ustaw(isbn="9788301000001"), "ciagle")


@pytest.mark.parametrize(
    "issn,e_issn,journal,oczekiwane",
    [
        ("1234-5678", "", {"issn": "12345678"}, set()),
        ("", "", {}, set()),
        # ISSN z PBN zapisany w BPP jako e-ISSN — zgodne, jak dotąd.
        ("", "1234-5678", {"issn": "1234-5678"}, set()),
        ("1234-5678", "8765-4321", {"issn": "1234-5678", "eissn": "87654321"}, set()),
        ("1234-5678", "", {"issn": "8765-4321"}, {"ISSN"}),
        ("1234-5678", "", {}, {"ISSN"}),
        # BYŁO: brak ISSN w BPP nie był zgłaszany, gdy PBN nie miał e-ISSN.
        # JEST: ISSN, który ma tylko PBN, jest różnicą.
        ("", "", {"issn": "1234-5678"}, {"ISSN"}),
        ("", "", {"issn": "1234-5678", "eissn": "8765-4321"}, {"ISSN", "e-ISSN"}),
        # BYŁO: zgodne, bo ISSN z BPP pasował do e-ISSN z PBN, choć ISSN
        # drukowanego z PBN w BPP nie było wcale.
        # JEST: brakujący w BPP numer jest różnicą (e-ISSN zgodny).
        ("1234-5678", "", {"issn": "0000-0000", "eissn": "1234-5678"}, {"ISSN"}),
        (
            "9999-9999",
            "1234-5678",
            {"issn": "0000-0000", "eissn": "1234-5678"},
            {"ISSN"},
        ),
    ],
)
def test_issn(para_ciagle, issn, e_issn, journal, oczekiwane):
    rekord, ustaw = para_ciagle
    rekord.issn, rekord.e_issn = issn, e_issn
    assert set(_roznice(ustaw(journal=journal), "ciagle", ["issn"])) == oczekiwane


def test_issn_z_pola_obiektu_ma_pierwszenstwo(para_ciagle):
    rekord, ustaw = para_ciagle
    rekord.issn = "1111-1111"
    roznice = _roznice(ustaw(issn="2222-2222", journal={"issn": "1111-1111"}), "ciagle")
    assert roznice["ISSN"] == ("1111-1111", "2222-2222")


@pytest.mark.parametrize(
    "public_www,www,pbn,rozni_sie",
    [
        ("https://a.pl/x", "", "https://a.pl/x", False),
        ("", "https://a.pl/x", "https://a.pl/x", False),
        ("", "", "", False),
        ("", "", "https://a.pl/x", True),
        ("", "https://b.pl/y", "https://a.pl/x", True),
        # BYŁO: różnica (liczył się tylko adres wolnego dostępu, gdy był).
        # JEST: zgodne — adres z PBN jest w jednym z dwóch pól adresu.
        ("https://b.pl/y", "https://a.pl/x", "https://a.pl/x", False),
        # BYŁO: różnica. JEST: zgodne — końcowy ukośnik nie ma znaczenia.
        ("https://a.pl/x", "", "https://a.pl/x/", False),
    ],
)
def test_adres_www(para_ciagle, public_www, www, pbn, rozni_sie):
    rekord, ustaw = para_ciagle
    rekord.public_www, rekord.www = public_www, www
    assert ("URL/WWW" in _roznice(ustaw(publicUri=pbn), "ciagle")) is rozni_sie


@pytest.mark.parametrize(
    "bpp,pbn,rozni_sie",
    [
        ("7", "7", False),
        ("7", " 7 ", False),
        ("7", "8", True),
        ("", None, False),
        # BYŁO: różnica tylko, gdy obie strony miały tom.
        # JEST: tom po jednej stronie też jest różnicą.
        ("", "8", True),
        ("7", None, True),
    ],
)
def test_tom(para_ciagle, bpp, pbn, rozni_sie):
    rekord, ustaw = para_ciagle
    rekord.tom = bpp
    assert ("Tom" in _roznice(ustaw(volume=pbn), "ciagle")) is rozni_sie


def test_tom_wydawnictwa_zwartego(para_zwarte):
    """BYŁO: tom porównywany tylko dla wydawnictw ciągłych.
    JEST: także dla zwartych (mają pole „tom”)."""
    rekord, ustaw = para_zwarte
    rekord.tom = "7"
    assert _roznice(ustaw(volume="8"), "zwarte")["Tom"] == ("7", "8")


@pytest.mark.parametrize(
    "bpp,pbn,rozni_sie",
    [
        ("", {}, False),
        # BYŁO: zakres stron czytany z pola ``pages`` (PBN podaje go
        # w ``pagesFromTo``) — praca z poprawnymi stronami była „różna”.
        # JEST: porównanie z ``pagesFromTo``.
        ("10-20", {"pagesFromTo": "10-20"}, False),
        ("10-20", {"pagesFromTo": "10-21"}, True),
        # BYŁO: półpauza zamiast łącznika = różnica. JEST: zgodne.
        ("10-20", {"pagesFromTo": "10–20"}, False),
        ("10-20", {"pagesFromTo": "10 - 20"}, False),
        # BYŁO: brak stron w BPP niezgłaszany (PBN nie miał ``pages``).
        # JEST: strony tylko w PBN (albo tylko w BPP) są różnicą.
        ("", {"pagesFromTo": "10-20"}, True),
        ("10-20", {}, True),
        # Pole ``pages`` nie jest zakresem stron — nie jest porównywane.
        ("10-20", {"pages": "10-20"}, True),
    ],
)
def test_strony(para_ciagle, bpp, pbn, rozni_sie):
    rekord, ustaw = para_ciagle
    rekord.strony = bpp
    assert ("Strony" in _roznice(ustaw(**pbn), "ciagle")) is rozni_sie


@pytest.mark.parametrize(
    "bpp,pbn,rozni_sie",
    [
        ("3", "3", False),
        ("", None, False),
        ("3", "4", True),
        ("", "4", True),
        ("3", None, True),
    ],
)
def test_numer_zeszytu(para_ciagle, bpp, pbn, rozni_sie):
    rekord, ustaw = para_ciagle
    rekord.nr_zeszytu = bpp
    assert ("Numer zeszytu" in _roznice(ustaw(issue=pbn), "ciagle")) is rozni_sie


def test_jezyk_porownywany_po_kodzie_z_pbn(para_ciagle):
    """BYŁO: nazwa języka z BPP porównywana z polem ``language`` (PBN podaje
    kod w ``mainLanguage``) — język prawie zawsze wychodził „różny”.
    JEST: kod z PBN jest zamieniany na język ze słownika BPP."""
    rekord, ustaw = para_ciagle
    assert rekord.jezyk.nazwa == "polski"
    assert "Język" not in _roznice(ustaw(mainLanguage="pol"), "ciagle")

    angielski = Jezyk.objects.get(skrot="ang.")
    angielski.pbn_uid = baker.make("pbn_api.Language", code="eng")
    angielski.save()
    assert _roznice(ustaw(mainLanguage="eng"), "ciagle")["Język"] == (
        "polski",
        "angielski",
    )
    # Brak języka w PBN też jest różnicą.
    assert _roznice(ustaw(mainLanguage=None), "ciagle")["Język"] == ("polski", "")


def test_jezyk_spoza_slownika_bpp(para_ciagle):
    """Kod, którego nie ma w słowniku języków BPP, jest pokazany wprost."""
    rekord, ustaw = para_ciagle
    assert _roznice(ustaw(mainLanguage="tlh"), "ciagle")["Język"] == ("polski", "tlh")


def test_streszczenie(para_ciagle):
    """BYŁO: streszczenia nie były porównywane wcale (kod szukał w rekordzie
    pola, którego nie ma). JEST: porównanie ze streszczeniami rekordu."""
    rekord, ustaw = para_ciagle
    tekst = "Bardzo długie streszczenie pracy."
    # Tylko w PBN.
    assert _roznice(ustaw(abstracts={"pol": tekst}), "ciagle")["Streszczenie"] == (
        "",
        tekst,
    )
    rekord.streszczenia.create(streszczenie=f"<p>{tekst}</p>")
    # To samo po obu stronach (znaczniki bez znaczenia).
    assert "Streszczenie" not in _roznice(ustaw(abstracts={"pol": tekst}), "ciagle")
    # Inne.
    assert "Streszczenie" in _roznice(ustaw(abstracts={"pol": "Inne."}), "ciagle")
    # Tylko w BPP.
    assert _roznice(ustaw(), "ciagle")["Streszczenie"] == (f"<p>{tekst}</p>", "")


def test_slowa_kluczowe(para_ciagle):
    """BYŁO: włączenie pola „Słowa kluczowe” kończyło się wyjątkiem
    (słowa kluczowe rekordu to tagi, nie tekst). JEST: porównanie zbiorów
    słów, bez względu na kolejność i wielkość liter — osobno słowa języka
    głównego i angielskie (rekord trzyma je w dwóch polach, PBN w podziale
    na języki)."""
    rekord, ustaw = para_ciagle
    slowa = {"pol": ["Chemia", "kryształy"], "eng": ["crystals"]}
    assert _roznice(ustaw(keywords=slowa), "ciagle", ["keywords"]) == {
        "Słowa kluczowe": ("", "Chemia, kryształy"),
        "Słowa kluczowe (ang.)": ("", "crystals"),
    }
    rekord.slowa_kluczowe.set(["kryształy", "chemia"])
    rekord.slowa_kluczowe_eng = ["Crystals"]
    assert _roznice(ustaw(keywords=slowa), "ciagle", ["keywords"]) == {}
    # Angielskie słowo wpisane w polu języka głównego to nie to samo.
    rekord.slowa_kluczowe.set(["kryształy", "chemia", "crystals"])
    rekord.slowa_kluczowe_eng = []
    assert set(_roznice(ustaw(keywords=slowa), "ciagle", ["keywords"])) == {
        "Słowa kluczowe",
        "Słowa kluczowe (ang.)",
    }
    # Słowa tylko w BPP.
    rekord.slowa_kluczowe.set(["chemia"])
    assert _roznice(ustaw(), "ciagle", ["keywords"]) == {
        "Słowa kluczowe": ("chemia", "")
    }
    # PBN podaje słowa jednym ciągiem — są dzielone.
    assert "Słowa kluczowe" not in _roznice(
        ustaw(keywords={"pol": ["chemia"], "eng": []}), "ciagle", ["keywords"]
    )
    rekord.slowa_kluczowe.set(["chemia", "sól"])
    assert (
        _roznice(ustaw(keywords={"pol": "chemia; sól"}), "ciagle", ["keywords"]) == {}
    )


def test_tylko_wlaczone_pola_sa_porownywane(para_ciagle):
    rekord, ustaw = para_ciagle
    rekord.tom = "7"
    rekord = ustaw(title="Inny tytuł", volume="8")
    assert set(_roznice(rekord, "ciagle", ["title"])) == {"Tytuł"}
    assert set(_roznice(rekord, "ciagle", ["volume"])) == {"Tom"}


def test_roznice_w_kolejnosci_pol_komparatora(para_ciagle):
    rekord, ustaw = para_ciagle
    rekord.tom = "7"
    wynik = PublicationComparisonView()._compare_publication(
        ustaw(title="Inny", volume="8", doi="10.1/x"),
        "ciagle",
        ["volume", "doi", "title"],
    )
    assert [r["field"] for r in wynik["differences"]] == ["Tytuł", "DOI", "Tom"]


def test_porownanie_wielu_prac_bez_zapytan_na_prace(
    wydawnictwo_ciagle, django_assert_num_queries
):
    """Komparator przelicza tysiące prac: przy danych dociągniętych z góry
    (relacje złączeniem, autorzy / słowa kluczowe / streszczenia jednym
    zapytaniem na paczkę) porównanie pól nie robi zapytań na pracę ani nie
    łączy się z PBN — działa na lokalnej kopii. Jedyne zapytania to
    wyszukanie języka dla kodu, raz na kod (tu: jeden nieznany kod — 4
    zapytania łącznie na 5 prac i wszystkie pola)."""
    from bpp.models import Wydawnictwo_Ciagle

    for nr in range(5):
        pbn = _pbn(
            title=f"Inny tytuł {nr}",
            year=2020,
            mainLanguage="eng",
            pagesFromTo="1-2",
            keywords={"pol": ["a"]},
            abstracts={"pol": "Streszczenie z PBN."},
            journal={"issn": "1234-5678"},
        )
        Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny=f"Praca {nr}",
            rok=2023,
            zrodlo=wydawnictwo_ciagle.zrodlo,
            jezyk=wydawnictwo_ciagle.jezyk,
            charakter_formalny=wydawnictwo_ciagle.charakter_formalny,
            typ_kbn=wydawnictwo_ciagle.typ_kbn,
            status_korekty=wydawnictwo_ciagle.status_korekty,
            pbn_uid=pbn,
        )
    prace = list(
        Wydawnictwo_Ciagle.objects.filter(pbn_uid__isnull=False)
        .select_related("pbn_uid", "zrodlo", "konferencja", "jezyk")
        .prefetch_related("autorzy_set", "slowa_kluczowe", "streszczenia")
    )
    assert len(prace) == 5
    komparator = PublicationComparisonView()

    with django_assert_num_queries(4):
        for praca in prace:
            # Pole po polu — tak woła porównanie przeliczanie w tle.
            for pole in WSZYSTKIE_POLA:
                komparator._compare_publication(praca, "ciagle", [pole])


# --- Pola spoza silnika wzbogacania: porównywane jak dotąd ------------------


def test_wydawca_ksiazki(para_zwarte):
    rekord, ustaw = para_zwarte
    rekord.wydawca_opis = "PWN"
    assert "Wydawca" not in _roznice(ustaw(publisher={"name": " PWN "}), "zwarte")
    assert _roznice(ustaw(publisher={"name": "WUW"}), "zwarte")["Wydawca"] == (
        "PWN",
        "WUW",
    )
    rekord.wydawca = baker.make("bpp.Wydawca", nazwa="Wydawca ze słownika")
    assert _roznice(ustaw(publisher={"name": "PWN"}), "zwarte")["Wydawca"] == (
        "Wydawca ze słownika",
        "PWN",
    )


def test_liczba_autorow(para_ciagle, jednostka):
    rekord, ustaw = para_ciagle
    rekord.dodaj_autora(
        baker.make("bpp.Autor", imiona="Jan", nazwisko="Kowalski"), jednostka
    )
    jeden = {"a" * 24: {"lastName": "Kowalski", "name": "Jan"}}
    dwoje = {**jeden, "b" * 24: {"lastName": "Nowak", "name": "Anna"}}
    assert "Liczba autorów" not in _roznice(ustaw(authors=jeden), "ciagle")
    assert _roznice(ustaw(authors=dwoje), "ciagle")["Liczba autorów"] == ("1", "2")
    # Redaktorzy liczą się razem z autorami.
    assert _roznice(ustaw(authors=jeden, editors=jeden), "ciagle")[
        "Liczba autorów"
    ] == ("1", "2")


def test_miejsce_wydania(para_zwarte):
    rekord, ustaw = para_zwarte
    rekord.miejsce_i_rok = "Warszawa 2023"
    assert "Miejsce wydania" not in _roznice(
        ustaw(publicationPlace="Warszawa"), "zwarte"
    )
    assert _roznice(ustaw(publicationPlace="Kraków"), "zwarte")["Miejsce wydania"] == (
        "Warszawa",
        "Kraków",
    )


def test_punkty(para_ciagle):
    rekord, ustaw = para_ciagle
    rekord.punkty_kbn = 100
    assert "Punkty" not in _roznice(ustaw(points=100.0), "ciagle")
    assert _roznice(ustaw(points=70), "ciagle")["Punkty"] == ("100.0", "70.0")
    assert _roznice(ustaw(), "ciagle")["Punkty"] == ("100.0", "0.0")


def test_konferencja_i_seria(para_ciagle, para_zwarte):
    rekord, ustaw = para_ciagle
    rekord.konferencja = baker.make("bpp.Konferencja", nazwa="Konferencja X")
    assert "Konferencja" not in _roznice(
        ustaw(conferenceName="Konferencja X"), "ciagle"
    )
    assert _roznice(ustaw(), "ciagle")["Konferencja"] == ("Konferencja X", "")
    rekord, ustaw = para_zwarte
    rekord.seria_wydawnicza = baker.make("bpp.Seria_Wydawnicza", nazwa="Seria Y")
    assert "Seria wydawnicza" not in _roznice(ustaw(series="Seria Y"), "zwarte")
    assert _roznice(ustaw(), "zwarte")["Seria wydawnicza"] == ("Seria Y", "")
