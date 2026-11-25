"""Testy charakteryzujące ``PublicationComparisonView._compare_publication``.

Przypinają OBECNE wyniki porównania pole po polu — także te, które wyglądają
na niedoskonałości (np. tytuł porównywany z dokładnością do odstępów, DOI
z prefiksem adresu traktowany jako inny). Służą jako siatka bezpieczeństwa
przy wydzielaniu wspólnych reguł porównywania (FD#517): refaktor nie może
zmienić żadnego z tych wyników.
"""

import pytest
from model_bakery import baker

from komparator_publikacji_pbn.views import (
    COMPARISON_FIELDS,
    PublicationComparisonView,
)
from pbn_api.models import Publication

pytestmark = pytest.mark.django_db

WSZYSTKIE_POLA = [p for p in COMPARISON_FIELDS if p != "keywords"]


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
    w.punkty_kbn = 0
    w.public_www = ""
    w.www = ""
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
        "language": rekord.jezyk.nazwa,
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


def test_wynik_zawiera_identyfikatory(para_ciagle):
    rekord, ustaw = para_ciagle
    wynik = PublicationComparisonView()._compare_publication(
        ustaw(title="Inny"), "ciagle", ["title"]
    )
    assert wynik["has_differences"] is True
    assert wynik["type"] == "ciagle"
    assert wynik["bpp_id"] == rekord.pk
    assert wynik["pbn_id"] == rekord.pbn_uid_id
    assert wynik["bpp_publication"] is rekord


@pytest.mark.parametrize(
    "bpp,pbn,rozni_sie",
    [
        ("Tytuł pracy", "Tytuł pracy", False),
        ("<i>Tytuł</i> pracy", "Tytuł pracy", False),
        ("  Tytuł pracy ", " Tytuł pracy  ", False),
        # Znaczniki są usuwane tylko po stronie BPP.
        ("Tytuł pracy", "<i>Tytuł</i> pracy", True),
        # Odstępy wewnątrz i wielkość liter mają znaczenie.
        ("Tytuł  pracy", "Tytuł pracy", True),
        ("Tytuł Pracy", "Tytuł pracy", True),
    ],
)
def test_tytul(para_ciagle, bpp, pbn, rozni_sie):
    rekord, ustaw = para_ciagle
    rekord.tytul_oryginalny = bpp
    assert ("Tytuł" in _roznice(ustaw(title=pbn), "ciagle")) is rozni_sie


def test_tytul_wartosci_sa_skracane_do_100_znakow(para_ciagle):
    rekord, ustaw = para_ciagle
    rekord.tytul_oryginalny = "A" * 150
    roznice = _roznice(ustaw(title="B" * 100), "ciagle")
    assert roznice["Tytuł"] == ("A" * 100 + "...", "B" * 100)


@pytest.mark.parametrize(
    "bpp,pbn,oczekiwane",
    [
        (2023, 2023, None),
        (2023, 2024, ("2023", "2024")),
        (2023, "2023", None),
        # Brak roku w PBN nie jest różnicą.
        (2023, None, None),
    ],
)
def test_rok(para_ciagle, bpp, pbn, oczekiwane):
    rekord, ustaw = para_ciagle
    rekord.rok = bpp
    rekord = ustaw(year=pbn)
    # ``year`` jest też kolumną kopii PBN (wyciąganą przy zapisie).
    assert _roznice(rekord, "ciagle").get("Rok") == oczekiwane


@pytest.mark.parametrize(
    "bpp,pbn,rozni_sie",
    [
        ("10.1/abc", "10.1/abc", False),
        ("10.1/ABC", " 10.1/abc ", False),
        (None, "", False),
        (None, "10.1/abc", True),
        ("10.1/abc", "", True),
        # Adres zamiast samego numeru to „inny” DOI.
        ("10.1/abc", "https://doi.org/10.1/abc", True),
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
        ("", "978-83-01-00000-1", "9788301000001", False),
        ("978-83-01-00000-1", "", "978-83-01-00000-2", True),
        ("", "", "9788301000001", True),
        ("978-83-01-00000-1", "", "", True),
        # Wielkość litery kontrolnej ma znaczenie.
        ("83-01-00000-x", "", "83-01-00000-X", True),
    ],
)
def test_isbn_ksiazki(para_zwarte, isbn, e_isbn, pbn, rozni_sie):
    rekord, ustaw = para_zwarte
    rekord.isbn, rekord.e_isbn = isbn, e_isbn
    assert ("ISBN" in _roznice(ustaw(isbn=pbn), "zwarte")) is rozni_sie


def test_isbn_nie_dotyczy_wydawnictw_ciaglych(para_ciagle):
    rekord, ustaw = para_ciagle
    assert "ISBN" not in _roznice(ustaw(isbn="9788301000001"), "ciagle")


@pytest.mark.parametrize(
    "issn,e_issn,journal,rozni_sie",
    [
        ("1234-5678", "", {"issn": "12345678"}, False),
        ("", "", {}, False),
        # ISSN z BPP pasuje do e-ISSN z PBN i odwrotnie.
        ("1234-5678", "", {"issn": "0000-0000", "eissn": "1234-5678"}, False),
        ("", "1234-5678", {"issn": "1234-5678"}, False),
        ("9999-9999", "1234-5678", {"issn": "0000-0000", "eissn": "1234-5678"}, False),
        ("1234-5678", "", {"issn": "8765-4321"}, True),
        ("1234-5678", "", {}, True),
        # Pusty ISSN w BPP „pasuje” do pustego e-ISSN z PBN — brak ISSN
        # w BPP nie jest zgłaszany, gdy PBN nie podaje e-ISSN.
        ("", "", {"issn": "1234-5678"}, False),
        ("", "", {"issn": "1234-5678", "eissn": "8765-4321"}, True),
    ],
)
def test_issn(para_ciagle, issn, e_issn, journal, rozni_sie):
    rekord, ustaw = para_ciagle
    rekord.issn, rekord.e_issn = issn, e_issn
    assert ("ISSN" in _roznice(ustaw(journal=journal), "ciagle")) is rozni_sie


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
        # Liczy się pierwsze niepuste: adres wolnego dostępu przed płatnym.
        ("https://b.pl/y", "https://a.pl/x", "https://a.pl/x", True),
        ("https://a.pl/x", "", "https://a.pl/x/", True),
        ("", "", "https://a.pl/x", True),
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
        # Różnica jest zgłaszana tylko, gdy obie strony mają tom.
        ("", "8", False),
        ("7", None, False),
    ],
)
def test_tom(para_ciagle, bpp, pbn, rozni_sie):
    rekord, ustaw = para_ciagle
    rekord.tom = bpp
    assert ("Tom" in _roznice(ustaw(volume=pbn), "ciagle")) is rozni_sie


def test_tom_nie_dotyczy_wydawnictw_zwartych(para_zwarte):
    rekord, ustaw = para_zwarte
    rekord.tom = "7"
    assert "Tom" not in _roznice(ustaw(volume="8"), "zwarte")


@pytest.mark.parametrize(
    "bpp,pbn,rozni_sie",
    [
        ("10-20", {"pages": "10-20"}, False),
        ("", {}, False),
        ("10-20", {"pages": "10-21"}, True),
        ("10-20", {"pages": "10–20"}, True),
        # Zakres stron z PBN (``pagesFromTo``) NIE jest brany pod uwagę.
        ("10-20", {"pagesFromTo": "10-20"}, True),
        ("", {"pagesFromTo": "10-20"}, False),
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


def test_jezyk_porownywany_po_nazwie_z_pola_language(para_ciagle):
    rekord, ustaw = para_ciagle
    nazwa = rekord.jezyk.nazwa
    assert "Język" not in _roznice(ustaw(language=nazwa.upper()), "ciagle")
    # Kod języka z PBN (``mainLanguage``) nie jest brany pod uwagę.
    assert _roznice(ustaw(language=None, mainLanguage="pol"), "ciagle")["Język"] == (
        nazwa,
        "",
    )


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


def test_streszczenie_nie_jest_porownywane(para_ciagle):
    """Rekord nie ma pola ``streszczenie`` (streszczenia są w osobnej tabeli)
    — porównanie streszczeń jest w obecnym kodzie martwe."""
    rekord, ustaw = para_ciagle
    rekord.streszczenia.create(streszczenie="Bardzo długie streszczenie pracy.")
    roznice = _roznice(ustaw(abstract="Zupełnie inne streszczenie."), "ciagle")
    assert not any(k.startswith("Streszczenie") for k in roznice)


def test_slowa_kluczowe_wywracaja_porownanie(para_ciagle):
    """Pole „Słowa kluczowe” (wyłączone domyślnie): ``slowa_kluczowe`` to
    menedżer tagów, a kod traktuje je jak tekst — włączenie tego pola kończy
    się wyjątkiem. Przypięte, żeby refaktor tego po cichu nie zmienił."""
    rekord, ustaw = para_ciagle
    with pytest.raises(AttributeError):
        _roznice(ustaw(keywords=["a"]), "ciagle", ["keywords"])


def test_tylko_wlaczone_pola_sa_porownywane(para_ciagle):
    rekord, ustaw = para_ciagle
    rekord.tom = "7"
    rekord = ustaw(title="Inny tytuł", volume="8")
    assert set(_roznice(rekord, "ciagle", ["title"])) == {"Tytuł"}
    assert set(_roznice(rekord, "ciagle", ["volume"])) == {"Tom"}
