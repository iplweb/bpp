"""FD#517: wzbogacanie istniejącego rekordu danymi z CrossRef / PBN.

Rekord już jest w bazie; redaktor widzi różnice pole po polu, zaznacza, co
przenieść, i zatwierdza. Nic nie zmienia się bez zaznaczenia, a przeniesienie
zostawia wpis w historii rekordu. Testy nie łączą się z siecią: dane CrossRef
są w pamięci podręcznej ``CrossrefAPICache``, dane PBN w lokalnej kopii.
"""

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import Permission
from django.urls import reverse
from model_bakery import baker
from reversion.models import Version

from bpp.models import Autor, Jezyk, Licencja_OpenAccess, Wydawnictwo_Ciagle
from crossref_bpp.models import CrossrefAPICache
from importer_publikacji.providers.crossref import CrossRefProvider
from importer_publikacji.wzbogacanie import zrodla
from importer_publikacji.wzbogacanie.autorzy import (
    BRAK_W_BPP as AUTOR_BRAK_W_BPP,
)
from importer_publikacji.wzbogacanie.autorzy import (
    INNA_KOLEJNOSC,
    TYLKO_W_BPP,
    ZGODNY,
    porownaj_autorow,
)
from importer_publikacji.wzbogacanie.pola import (
    BRAK_W_BPP,
    BRAK_W_ZRODLE,
    NIEROZPOZNANE,
    ROZNE,
    ZGODNE,
    porownaj,
    zastosuj,
)

pytestmark = pytest.mark.django_db

DOI = "10.1234/test.2024.001"


@pytest.fixture
def rekord(wydawnictwo_ciagle):
    """Rekord częściowo zgodny z ``sample_crossref_data``: ten sam DOI
    i tom, inny tytuł i strony, bez numeru zeszytu i adresu WWW."""
    w = wydawnictwo_ciagle
    w.tytul_oryginalny = "Test Publication Titel"
    w.doi = DOI
    w.rok = 2024
    w.tom = "42"
    w.nr_zeszytu = ""
    w.strony = "100-111"
    w.www = ""
    w.issn = "1234-5678"
    w.jezyk = Jezyk.objects.get(skrot_crossref="en")
    w.uwagi = "nie ruszać"
    w.save()
    return w


@pytest.fixture
def crossref(sample_crossref_data):
    """Odpowiedź CrossRef w pamięci podręcznej — bez sieci."""
    CrossrefAPICache.objects.create(doi=DOI, data=sample_crossref_data)
    return sample_crossref_data


def _url(rekord, zrodlo="crossref"):
    return reverse("admin:bpp_wydawnictwo_ciagle_wzbogac", args=(rekord.pk, zrodlo))


def _po_kluczu(wiersze):
    return {w.klucz: w for w in wiersze}


def _wiersze(rekord):
    return porownaj(rekord, CrossRefProvider().fetch(DOI))


def test_porownanie_statusy_pol(rekord, crossref):
    w = _po_kluczu(_wiersze(rekord))

    assert w["doi"].status == ZGODNE
    assert w["tom"].status == ZGODNE
    assert w["rok"].status == ZGODNE
    assert w["issn"].status == ZGODNE
    assert w["jezyk"].status == ZGODNE
    assert w["tytul_oryginalny"].status == ROZNE
    assert w["strony"].status == ROZNE
    assert w["nr_zeszytu"].status == BRAK_W_BPP
    assert w["www"].status == BRAK_W_BPP
    assert w["slowa_kluczowe"].status == BRAK_W_BPP
    # Zgodnych pól nie da się „przenieść”, różniące się — tak.
    assert not w["doi"].mozna_przeniesc
    assert w["strony"].mozna_przeniesc
    # W długich tekstach różnica jest pokazana na poziomie słów.
    assert "<del>Titel</del>" in w["tytul_oryginalny"].zmiana
    assert "<ins>Title</ins>" in w["tytul_oryginalny"].zmiana


def test_porownanie_brak_w_zrodle(rekord, crossref):
    rekord.e_issn = "9999-0000"
    rekord.save()

    w = _po_kluczu(_wiersze(rekord))

    assert w["e_issn"].status == BRAK_W_ZRODLE
    assert not w["e_issn"].mozna_przeniesc


def test_porownanie_ignoruje_roznice_zapisu(rekord, crossref):
    """Kreski w ISSN, wielkość liter DOI, półpauza w stronach, znaczniki
    HTML w tytule — to nie są różnice."""
    rekord.tytul_oryginalny = "<i>Test</i>  Publication Title"
    rekord.doi = DOI.upper()
    rekord.issn = "12345678"
    rekord.strony = "100–110"
    rekord.save()

    w = _po_kluczu(_wiersze(rekord))

    for klucz in ("tytul_oryginalny", "doi", "issn", "strony"):
        assert w[klucz].status == ZGODNE, klucz


def test_issn_zapisany_w_bpp_jako_e_issn_jest_zgodny(rekord, crossref):
    rekord.issn = ""
    rekord.e_issn = "1234-5678"
    rekord.save()

    w = _po_kluczu(_wiersze(rekord))

    assert w["issn"].status == ZGODNE
    assert "e-ISSN" in w["issn"].uwaga


def test_adres_doi_org_nie_jest_przenoszony_do_www(rekord, crossref):
    crossref["resource"]["primary"]["URL"] = f"https://doi.org/{DOI}"
    CrossrefAPICache.objects.filter(doi=DOI).update(data=crossref)

    w = _po_kluczu(_wiersze(rekord))

    assert w["www"].status == BRAK_W_BPP
    assert not w["www"].mozna_przeniesc
    assert "nie da się zapisać" in w["www"].uwaga


def test_nieznany_jezyk_nie_jest_przenoszony(rekord, crossref):
    crossref["language"] = "tlh"
    CrossrefAPICache.objects.filter(doi=DOI).update(data=crossref)

    w = _po_kluczu(_wiersze(rekord))

    assert w["jezyk"].status == NIEROZPOZNANE
    assert not w["jezyk"].mozna_przeniesc


def test_zastosuj_przenosi_tylko_wybrane(rekord, crossref):
    w = _po_kluczu(_wiersze(rekord))

    przeniesione, pominiete = zastosuj(
        rekord, w.values(), [w["strony"].wartosc_wyboru, w["www"].wartosc_wyboru]
    )

    assert [x.klucz for x in przeniesione] == ["strony", "www"]
    assert pominiete == []
    rekord.refresh_from_db()
    assert rekord.strony == "100-110"
    assert rekord.www == "https://example.com/article"
    # Niezaznaczone różnice i pola spoza porównania zostają.
    assert rekord.tytul_oryginalny == "Test Publication Titel"
    assert rekord.nr_zeszytu == ""
    assert rekord.uwagi == "nie ruszać"


def test_zastosuj_pomija_gdy_zrodlo_zmienilo_sie_od_podgladu(rekord, crossref):
    wybor = _po_kluczu(_wiersze(rekord))["strony"].wartosc_wyboru
    crossref["page"] = "200-210"
    CrossrefAPICache.objects.filter(doi=DOI).update(data=crossref)

    przeniesione, pominiete = zastosuj(rekord, _wiersze(rekord), [wybor])

    assert przeniesione == []
    assert [x.klucz for x in pominiete] == ["strony"]
    rekord.refresh_from_db()
    assert rekord.strony == "100-111"


def test_zastosuj_slowa_kluczowe_streszczenie_licencje(
    rekord, crossref, openaccess_data
):
    crossref["abstract"] = "Streszczenie pracy po polsku, z ogonkami: ąęść."
    CrossrefAPICache.objects.filter(doi=DOI).update(data=crossref)
    w = _po_kluczu(_wiersze(rekord))
    assert w["openaccess_licencja"].status == BRAK_W_BPP
    assert w["streszczenie-0"].status == BRAK_W_BPP

    zastosuj(
        rekord,
        w.values(),
        [
            w[k].wartosc_wyboru
            for k in ("slowa_kluczowe", "streszczenie-0", "openaccess_licencja")
        ],
    )

    rekord.refresh_from_db()
    assert list(rekord.slowa_kluczowe.names()) == ["Computer Science"]
    assert rekord.openaccess_licencja == Licencja_OpenAccess.objects.get(skrot="CC-BY")
    streszczenie = rekord.streszczenia.get()
    assert streszczenie.streszczenie.startswith("Streszczenie pracy")
    assert streszczenie.jezyk_streszczenia == Jezyk.objects.get(skrot_crossref="pl")
    # Po przeniesieniu nie ma już czego przenosić.
    po = _po_kluczu(_wiersze(rekord))
    assert po["slowa_kluczowe"].status == ZGODNE
    assert po["streszczenie-0"].status == ZGODNE
    assert po["openaccess_licencja"].status == ZGODNE


def test_istniejace_streszczenie_zostaje_nowe_jest_dodawane(rekord, crossref):
    rekord.streszczenia.create(streszczenie="Stare streszczenie.")
    crossref["abstract"] = "A completely different abstract."
    CrossrefAPICache.objects.filter(doi=DOI).update(data=crossref)
    w = _po_kluczu(_wiersze(rekord))
    assert w["streszczenie-0"].status == ROZNE

    zastosuj(rekord, w.values(), [w["streszczenie-0"].wartosc_wyboru])

    assert sorted(rekord.streszczenia.values_list("streszczenie", flat=True)) == [
        "A completely different abstract.",
        "Stare streszczenie.",
    ]


def test_widok_pokazuje_liste_roznic(admin_client, rekord, crossref, openaccess_data):
    res = admin_client.get(_url(rekord))

    assert res.status_code == 200
    tresc = res.content.decode()
    # Tytuł, nr zeszytu, strony, adres WWW, licencja, słowa kluczowe.
    assert "Różni się 6 pól" in tresc
    assert "Zaznacz wszystkie różnice" in tresc
    assert "Przenieś zaznaczone pola do BPP" in tresc
    assert "<del>Titel</del>" in tresc
    # Samo otwarcie podglądu niczego nie zmienia.
    rekord.refresh_from_db()
    assert rekord.strony == "100-111"
    assert not Version.objects.get_for_object(rekord).exists()


def test_widok_wszystko_sie_zgadza(admin_client, rekord, crossref):
    w = _po_kluczu(_wiersze(rekord))
    zastosuj(rekord, w.values(), [x.wartosc_wyboru for x in w.values()])

    res = admin_client.get(_url(rekord))

    tresc = res.content.decode()
    assert "Wszystko się zgadza" in tresc
    assert "Przenieś zaznaczone pola do BPP" not in tresc


def test_widok_przenosi_wybrane_pola_i_zapisuje_historie(
    admin_client, admin_user, rekord, crossref
):
    w = _po_kluczu(_wiersze(rekord))

    res = admin_client.post(
        _url(rekord),
        {"pole": [w["strony"].wartosc_wyboru, w["nr_zeszytu"].wartosc_wyboru]},
        follow=True,
    )

    assert res.status_code == 200
    rekord.refresh_from_db()
    assert rekord.strony == "100-110"
    assert rekord.nr_zeszytu == "3"
    assert rekord.tytul_oryginalny == "Test Publication Titel"

    opis = "Wzbogacono z CrossRef: pola Strony, Nr zeszytu"
    wpis = LogEntry.objects.get(object_id=str(rekord.pk), action_flag=CHANGE)
    assert wpis.user == admin_user
    assert wpis.change_message == opis
    # Historia rekordu pokazuje wersje: stan sprzed zmiany i po niej.
    wersje = list(Version.objects.get_for_object(rekord))
    assert len(wersje) == 2
    assert wersje[0].revision.comment == opis
    assert wersje[0].revision.user == admin_user
    assert wersje[0].field_dict["strony"] == "100-110"
    assert wersje[1].field_dict["strony"] == "100-111"
    assert opis in res.content.decode()


def test_widok_bez_zaznaczenia_nic_nie_zmienia(admin_client, rekord, crossref):
    res = admin_client.post(_url(rekord), {}, follow=True)

    assert "Nie zaznaczono żadnego pola" in res.content.decode()
    rekord.refresh_from_db()
    assert rekord.strony == "100-111"
    assert not LogEntry.objects.filter(object_id=str(rekord.pk)).exists()
    assert not Version.objects.get_for_object(rekord).exists()


def test_widok_rekord_bez_doi(admin_client, rekord):
    Wydawnictwo_Ciagle.objects.filter(pk=rekord.pk).update(doi=None)

    res = admin_client.get(_url(rekord))

    assert "Rekord nie ma numeru DOI" in res.content.decode()


def test_widok_rekord_bez_odpowiednika_pbn(admin_client, rekord):
    res = admin_client.get(_url(rekord, "pbn"))

    assert "Rekord nie ma odpowiednika w PBN" in res.content.decode()


def test_widok_nieznane_zrodlo(admin_client, rekord):
    assert admin_client.get(_url(rekord, "scopus")).status_code == 404


def test_widok_wymaga_prawa_zmiany_rekordu(client, rekord, crossref):
    user = baker.make("bpp.BppUser", is_staff=True, is_active=True)
    user.user_permissions.add(
        Permission.objects.get(codename="view_wydawnictwo_ciagle")
    )
    client.force_login(user)
    wybor = _po_kluczu(_wiersze(rekord))["strony"].wartosc_wyboru

    assert client.get(_url(rekord)).status_code == 403
    assert client.post(_url(rekord), {"pole": [wybor]}).status_code == 403
    rekord.refresh_from_db()
    assert rekord.strony == "100-111"


def test_przyciski_w_formularzu_rekordu(admin_client, rekord, pbn_publication):
    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=(rekord.pk,))

    tresc = admin_client.get(url).content.decode()
    assert "Wzbogać z CrossRef" in tresc
    assert "Wzbogać z PBN" not in tresc

    Wydawnictwo_Ciagle.objects.filter(pk=rekord.pk).update(
        doi=None, pbn_uid=pbn_publication
    )
    tresc = admin_client.get(url).content.decode()
    assert "Wzbogać z CrossRef" not in tresc
    assert "Wzbogać z PBN" in tresc
    # Dotychczasowe przyciski odpowiednika w PBN zostają.
    assert "Kopia PBN" in tresc


def test_wydawnictwo_zwarte_isbn(admin_client, wydawnictwo_zwarte, crossref):
    crossref["type"] = "book"
    crossref["isbn-type"] = [{"type": "print", "value": "978-83-01-00000-1"}]
    CrossrefAPICache.objects.filter(doi=DOI).update(data=crossref)
    wydawnictwo_zwarte.doi = DOI
    wydawnictwo_zwarte.isbn = ""
    wydawnictwo_zwarte.save()
    w = _po_kluczu(porownaj(wydawnictwo_zwarte, CrossRefProvider().fetch(DOI)))
    assert w["isbn"].status == BRAK_W_BPP
    # Wydawnictwo zwarte nie ma pola „nr zeszytu” — nie ma takiego wiersza.
    assert "nr_zeszytu" not in w
    url = reverse(
        "admin:bpp_wydawnictwo_zwarte_wzbogac", args=(wydawnictwo_zwarte.pk, "crossref")
    )

    admin_client.post(url, {"pole": [w["isbn"].wartosc_wyboru]})

    wydawnictwo_zwarte.refresh_from_db()
    assert wydawnictwo_zwarte.isbn == "978-83-01-00000-1"


def _autor(rekord, jednostka, imiona, nazwisko, **kw):
    autor = baker.make(Autor, imiona=imiona, nazwisko=nazwisko, **kw)
    rekord.dodaj_autora(autor, jednostka)
    return autor


def test_autorzy_brakujacy_nadmiarowi_i_kolejnosc(rekord, jednostka):
    _autor(rekord, jednostka, "Anna", "Nowak")
    _autor(rekord, jednostka, "Jan", "Kowalski", orcid="0000-0001-2345-6789")
    _autor(rekord, jednostka, "Zenon", "Nadmiarowy")
    osoby = [
        # Dopasowany po ORCID mimo innego zapisu nazwiska.
        {"family": "Kowalsky", "given": "J.", "orcid": "0000-0001-2345-6789"},
        {"family": "Nowak", "given": "A."},
        {"family": "Brakujący", "given": "Piotr"},
    ]

    wynik = porownaj_autorow(rekord, osoby)

    statusy = [(w.zrodlo or w.bpp, w.status) for w in wynik.wiersze]
    assert statusy == [
        ("Kowalsky J.", ZGODNY),
        ("Nowak A.", INNA_KOLEJNOSC),
        ("Brakujący Piotr", AUTOR_BRAK_W_BPP),
        ("Nadmiarowy Zenon", TYLKO_W_BPP),
    ]
    assert wynik.wiersze[0].sposob == "ORCID"
    assert (wynik.brakujacy, wynik.nadmiarowi, wynik.inna_kolejnosc) == (1, 1, 1)
    assert wynik.sa_roznice


def test_autorzy_sa_tylko_do_podgladu(admin_client, rekord, crossref, jednostka):
    _autor(rekord, jednostka, "Jan", "Kowalski")

    tresc = admin_client.get(_url(rekord)).content.decode()

    assert "Autorzy — tylko do podglądu" in tresc
    assert "Brakuje w BPP: <strong>1</strong>" in tresc
    assert rekord.autorzy_set.count() == 1


def test_crossref_niedostepny_daje_czytelny_komunikat(admin_client, rekord, mocker):
    import requests

    mocker.patch.object(
        zrodla.CrossRefProvider, "fetch", side_effect=requests.ConnectionError("x")
    )

    res = admin_client.get(_url(rekord))

    assert res.status_code == 200
    assert "Nie udało się połączyć z CrossRef" in res.content.decode()
