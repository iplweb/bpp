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
#: Wartość ukrytego pola formularza: publikacja w źródle z podglądu.
ZID = f"doi:{DOI}"


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
        {
            "zrodlo_id": ZID,
            "pole": [w["strony"].wartosc_wyboru, w["nr_zeszytu"].wartosc_wyboru],
        },
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
    assert (
        client.post(_url(rekord), {"zrodlo_id": ZID, "pole": [wybor]}).status_code
        == 403
    )
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

    admin_client.post(url, {"zrodlo_id": ZID, "pole": [w["isbn"].wartosc_wyboru]})

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


def test_autorzy_podglad_niczego_nie_zmienia(admin_client, rekord, crossref, jednostka):
    _autor(rekord, jednostka, "Jan", "Kowalski")

    tresc = admin_client.get(_url(rekord)).content.decode()

    assert "<h2>Autorzy</h2>" in tresc
    assert "Brakuje w BPP: <strong>1</strong>" in tresc
    assert rekord.autorzy_set.count() == 1


def test_crossref_niedostepny_daje_czytelny_komunikat(admin_client, rekord, mocker):
    """Brak danych w pamięci podręcznej: jedno zapytanie do CrossRef
    z krótkim limitem czasu; błąd połączenia to komunikat, nie awaria."""
    import requests

    from crossref_bpp.monkey_patches import PatchedWorks

    limity = []

    def doi(self, doi, **kw):
        limity.append(self.timeout)
        raise requests.ConnectTimeout("brak sieci")

    mocker.patch.object(PatchedWorks, "doi", doi)

    res = admin_client.get(_url(rekord))

    assert res.status_code == 200
    assert "Nie udało się pobrać danych z CrossRef" in res.content.decode()
    assert limity == [zrodla.LIMIT_CZASU_CROSSREF]


def test_podglad_crossref_pokazuje_date_danych_i_nie_pyta_crossref(
    admin_client, rekord, crossref, mocker
):
    from crossref_bpp.monkey_patches import PatchedWorks

    siec = mocker.patch.object(PatchedWorks, "doi")

    tresc = admin_client.get(_url(rekord)).content.decode()

    assert "Dane pobrane z CrossRef" in tresc
    assert "Odśwież z CrossRef" in tresc
    siec.assert_not_called()


def test_odswiez_z_crossref(admin_client, rekord, crossref, mocker):
    from crossref_bpp.monkey_patches import PatchedWorks

    mocker.patch.object(PatchedWorks, "doi", return_value={**crossref, "page": "7-9"})

    res = admin_client.post(_url(rekord), {"odswiez": "1"}, follow=True)

    assert "Pobrano aktualne dane z CrossRef" in res.content.decode()
    assert CrossrefAPICache.objects.get(doi=DOI).data["page"] == "7-9"
    assert _po_kluczu(_wiersze(rekord))["strony"].zrodlo == "7-9"


def test_nieudane_odswiezenie_crossref_zostawia_poprzednie_dane(
    admin_client, rekord, crossref, mocker
):
    import requests

    from crossref_bpp.monkey_patches import PatchedWorks

    mocker.patch.object(PatchedWorks, "doi", side_effect=requests.ConnectionError("x"))

    res = admin_client.post(_url(rekord), {"odswiez": "1"}, follow=True)

    tresc = res.content.decode()
    assert "Nie udało się pobrać danych z CrossRef" in tresc
    assert "Pokazuję dane pobrane wcześniej" in tresc
    assert CrossrefAPICache.objects.get(doi=DOI).data["page"] == "100-110"


def test_rekord_zmieniony_od_podgladu_nie_jest_nadpisywany(
    admin_client, rekord, crossref
):
    """Inny redaktor poprawił pole między podglądem a zatwierdzeniem — jego
    zmiana nie jest po cichu nadpisywana."""
    wybor = _po_kluczu(_wiersze(rekord))["strony"].wartosc_wyboru
    Wydawnictwo_Ciagle.objects.filter(pk=rekord.pk).update(strony="100-112")

    res = admin_client.post(
        _url(rekord), {"zrodlo_id": ZID, "pole": [wybor]}, follow=True
    )

    rekord.refresh_from_db()
    assert rekord.strony == "100-112"
    assert "zmieniły się od podglądu" in res.content.decode()
    assert not LogEntry.objects.filter(object_id=str(rekord.pk)).exists()


def test_powtorzone_pole_w_formularzu_nie_dubluje_streszczenia(
    admin_client, rekord, crossref
):
    crossref["abstract"] = "Jedno streszczenie."
    CrossrefAPICache.objects.filter(doi=DOI).update(data=crossref)
    wybor = _po_kluczu(_wiersze(rekord))["streszczenie-0"].wartosc_wyboru

    admin_client.post(_url(rekord), {"zrodlo_id": ZID, "pole": [wybor, wybor, wybor]})

    assert rekord.streszczenia.count() == 1


def test_slowa_kluczowe_crossref_dopisuja_brakujace(rekord, crossref):
    """CrossRef nie dzieli słów na języki: porównanie ze wszystkimi słowami
    rekordu, przeniesienie dopisuje brakujące i nie usuwa wpisanych ręcznie."""
    crossref["subject"] = ["Computer Science", "Crystals"]
    CrossrefAPICache.objects.filter(doi=DOI).update(data=crossref)
    rekord.slowa_kluczowe.set(["ręczne"])
    rekord.slowa_kluczowe_eng = ["crystals"]
    rekord.save()
    w = _po_kluczu(_wiersze(rekord))
    assert w["slowa_kluczowe"].status == ROZNE

    zastosuj(rekord, w.values(), [w["slowa_kluczowe"].wartosc_wyboru])

    rekord.refresh_from_db()
    assert sorted(rekord.slowa_kluczowe.names()) == ["Computer Science", "ręczne"]
    assert rekord.slowa_kluczowe_eng == ["crystals"]


# --- Dodawanie brakujących autorów przez krok „Autorzy” importera -----------


def _url_autorzy(rekord, zrodlo="crossref"):
    return reverse(
        "admin:bpp_wydawnictwo_ciagle_wzbogac_autorzy", args=(rekord.pk, zrodlo)
    )


@pytest.fixture
def sesja_autorow(admin_client, rekord, crossref, jednostka, uczelnia):
    """Rekord ma Kowalskiego; w CrossRef jest jeszcze Nowak Anna — sesja
    importera z samą brakującą osobą, otwarta przyciskiem z porównania."""
    from importer_publikacji.models import ImportSession

    _autor(rekord, jednostka, "Jan", "Kowalski")
    res = admin_client.post(_url_autorzy(rekord))
    session = ImportSession.objects.get()
    assert res.status_code == 302
    assert res.url == reverse(
        "importer_publikacji:authors", kwargs={"session_id": session.pk}
    )
    return session


def test_przycisk_dodawania_brakujacych_autorow(
    admin_client, rekord, crossref, jednostka
):
    _autor(rekord, jednostka, "Jan", "Kowalski")

    tresc = admin_client.get(_url(rekord)).content.decode()

    assert "Dodaj brakujących autorów (1) w importerze" in tresc
    assert _url_autorzy(rekord) in tresc


def test_sesja_autorow_zawiera_tylko_brakujace_osoby(sesja_autorow, rekord):
    from importer_publikacji.wzbogacanie.dodawanie_autorow import (
        jest_sesja_wzbogacania,
        rekord_sesji,
    )

    assert jest_sesja_wzbogacania(sesja_autorow)
    assert rekord_sesji(sesja_autorow) == rekord
    assert sesja_autorow.status == sesja_autorow.Status.SOURCE_MATCHED
    assert sesja_autorow.normalized_data["year"] == rekord.rok
    assert [(a.family_name, a.given_name) for a in sesja_autorow.authors.all()] == [
        ("Nowak", "Anna")
    ]


def test_krok_autorzy_mowi_ze_to_istniejacy_rekord(admin_client, sesja_autorow):
    url = reverse(
        "importer_publikacji:authors", kwargs={"session_id": sesja_autorow.pk}
    )

    tresc = admin_client.get(url).content.decode()

    assert "istniejącego rekordu" in tresc
    assert "Dodaj autorów do rekordu" in tresc
    assert "Potwierdź i przejdź dalej" not in tresc


def test_zwykla_sesja_importu_ma_krok_autorzy_bez_zmian(admin_client, uczelnia):
    from importer_publikacji.models import ImportSession

    session = baker.make(
        ImportSession,
        uczelnia=uczelnia,
        status=ImportSession.Status.SOURCE_MATCHED,
        normalized_data={"title": "X", "year": 2024},
        raw_data={},
        matched_data={},
    )
    url = reverse("importer_publikacji:authors", kwargs={"session_id": session.pk})

    tresc = admin_client.get(url).content.decode()

    assert "Potwierdź i przejdź dalej" in tresc
    assert "istniejącego rekordu" not in tresc
    assert "Dodaj autorów do rekordu" not in tresc


def test_potwierdzenie_dodaje_autora_do_istniejacego_rekordu(
    admin_client, admin_user, sesja_autorow, rekord, jednostka
):
    from importer_publikacji.models import ImportedAuthor, ImportSession

    nowak = baker.make(Autor, imiona="Anna", nazwisko="Nowak")
    ia = sesja_autorow.authors.get()
    ia.matched_autor = nowak
    ia.matched_jednostka = jednostka
    ia.match_status = ImportedAuthor.MatchStatus.MANUAL
    ia.save()
    ile_rekordow = Wydawnictwo_Ciagle.objects.count()

    res = admin_client.post(
        reverse(
            "importer_publikacji:authors-confirm",
            kwargs={"session_id": sesja_autorow.pk},
        ),
        HTTP_HX_REQUEST="true",
    )

    # Wracamy do porównania; nowy rekord nie powstał, sesja nie zostaje.
    assert res["HX-Redirect"] == _url(rekord)
    assert Wydawnictwo_Ciagle.objects.count() == ile_rekordow
    assert not ImportSession.objects.exists()
    autorzy = list(
        rekord.autorzy_set.order_by("kolejnosc").values_list(
            "autor__nazwisko", flat=True
        )
    )
    assert autorzy == ["Kowalski", "Nowak"]
    wpis = LogEntry.objects.get(object_id=str(rekord.pk), action_flag=CHANGE)
    assert wpis.user == admin_user
    assert wpis.change_message == (
        f"Dodano autorów z CrossRef (kreator importera publikacji): {nowak}"
    )
    assert Version.objects.get_for_object(rekord).first().revision.comment == (
        wpis.change_message
    )
    # Po dodaniu listy autorów się zgadzają.
    assert "Lista autorów się zgadza" in admin_client.get(_url(rekord)).content.decode()


def test_niedopasowana_osoba_blokuje_dodanie(admin_client, sesja_autorow, rekord):
    sesja_autorow.authors.update(matched_autor=None)

    res = admin_client.post(
        reverse(
            "importer_publikacji:authors-confirm",
            kwargs={"session_id": sesja_autorow.pk},
        ),
        HTTP_HX_REQUEST="true",
    )

    assert "niedopasowany autor" in res.content.decode()
    assert rekord.autorzy_set.count() == 1


def test_autor_ktory_juz_jest_w_rekordzie_nie_jest_dublowany(
    admin_client, sesja_autorow, rekord, jednostka
):
    from importer_publikacji.models import ImportedAuthor, ImportSession

    kowalski = rekord.autorzy_set.get().autor
    sesja_autorow.authors.update(
        matched_autor=kowalski,
        matched_jednostka=jednostka,
        match_status=ImportedAuthor.MatchStatus.MANUAL,
    )

    res = admin_client.post(
        reverse(
            "importer_publikacji:authors-confirm",
            kwargs={"session_id": sesja_autorow.pk},
        ),
        HTTP_HX_REQUEST="true",
    )

    assert "są już na liście autorów rekordu" in res.content.decode()
    assert rekord.autorzy_set.count() == 1
    assert ImportSession.objects.exists()
    assert not LogEntry.objects.filter(object_id=str(rekord.pk)).exists()


def test_sesja_dodawania_autorow_nie_tworzy_nowego_rekordu(sesja_autorow):
    from django.core.exceptions import ValidationError

    from importer_publikacji.views.publikacja import _create_publication

    ile = Wydawnictwo_Ciagle.objects.count()

    with pytest.raises(ValidationError, match="nie tworzy"):
        _create_publication(sesja_autorow)

    assert Wydawnictwo_Ciagle.objects.count() == ile


def test_dodawanie_autorow_wymaga_uprawnien_importera(client, rekord, crossref):
    from importer_publikacji.models import ImportSession

    user = baker.make("bpp.BppUser", is_staff=True, is_active=True)
    user.user_permissions.add(
        Permission.objects.get(codename="change_wydawnictwo_ciagle")
    )
    client.force_login(user)

    assert client.post(_url_autorzy(rekord)).status_code == 403
    assert not ImportSession.objects.exists()
    tresc = client.get(_url(rekord)).content.decode()
    assert "w importerze</button>" not in tresc
    assert "wymaga uprawnień do importera publikacji" in tresc


def test_ponowne_klikniecie_nie_mnozy_sesji(admin_client, sesja_autorow, rekord):
    from importer_publikacji.models import ImportSession

    admin_client.post(_url_autorzy(rekord))
    admin_client.post(_url_autorzy(rekord))

    assert ImportSession.objects.count() == 1
    assert ImportSession.objects.get().pk != sesja_autorow.pk


def test_powrot_bez_dodawania_usuwa_sesje(admin_client, sesja_autorow, rekord):
    from importer_publikacji.models import ImportSession

    url = reverse(
        "importer_publikacji:authors", kwargs={"session_id": sesja_autorow.pk}
    )
    assert f'name="porzuc" value="{sesja_autorow.pk}"' in (
        admin_client.get(url).content.decode()
    )

    res = admin_client.post(_url_autorzy(rekord), {"porzuc": sesja_autorow.pk})

    assert res.status_code == 302
    assert res.url == _url(rekord)
    assert not ImportSession.objects.exists()
    assert rekord.autorzy_set.count() == 1


def test_porzucenie_nie_usuwa_zwyklej_sesji_importu(
    admin_client, admin_user, rekord, crossref, uczelnia
):
    from importer_publikacji.models import ImportSession

    zwykla = baker.make(
        ImportSession,
        created_by=admin_user,
        uczelnia=uczelnia,
        status=ImportSession.Status.SOURCE_MATCHED,
        normalized_data={},
        raw_data={},
        matched_data={},
    )

    admin_client.post(_url_autorzy(rekord), {"porzuc": zwykla.pk})

    assert ImportSession.objects.filter(pk=zwykla.pk).exists()


def _dopasuj_nowaka(sesja, jednostka):
    from importer_publikacji.models import ImportedAuthor

    nowak = baker.make(Autor, imiona="Anna", nazwisko="Nowak")
    sesja.authors.update(
        matched_autor=nowak,
        matched_jednostka=jednostka,
        match_status=ImportedAuthor.MatchStatus.MANUAL,
    )
    return reverse(
        "importer_publikacji:authors-confirm", kwargs={"session_id": sesja.pk}
    )


def test_potwierdzenie_sprawdza_ponownie_prawo_zmiany_rekordu(
    admin_client, sesja_autorow, rekord, jednostka, mocker
):
    """Uprawnienia mogły się zmienić od otwarcia kroku „Autorzy” — przy
    potwierdzaniu prawo zmiany rekordu jest sprawdzane jeszcze raz."""
    from django.contrib import admin

    potwierdz = _dopasuj_nowaka(sesja_autorow, jednostka)
    mocker.patch.object(
        type(admin.site._registry[Wydawnictwo_Ciagle]),
        "has_change_permission",
        return_value=False,
    )

    res = admin_client.post(potwierdz, HTTP_HX_REQUEST="true")

    assert "Nie masz uprawnień do zmiany tego rekordu" in res.content.decode()
    assert rekord.autorzy_set.count() == 1


def test_potwierdzenie_odmawia_dla_rekordu_w_koszu(
    admin_client, sesja_autorow, rekord, jednostka
):
    potwierdz = _dopasuj_nowaka(sesja_autorow, jednostka)
    rekord.delete()

    res = admin_client.post(potwierdz, HTTP_HX_REQUEST="true")

    tresc = res.content.decode()
    assert "już nie istnieje" in tresc or "Rekord jest w koszu" in tresc
    assert (
        not type(rekord)
        ._base_manager.get(pk=rekord.pk)
        .autorzy_set.filter(autor__nazwisko="Nowak")
        .exists()
    )
