"""FD#518: porównanie rekordu z wcześniejszą wersją publikacji w PBN
i odtworzenie z niej wybranych pól (w widoku wzbogacania z FD#517).

PBN przechowuje historię wersji publikacji; lokalna kopia (``Publication.
versions``) ma je wszystkie. Testy nie łączą się z PBN — klient jest atrapą
udostępniającą wyłącznie odczyt jednej publikacji.
"""

import copy
from unittest.mock import MagicMock

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.urls import reverse
from model_bakery import baker
from reversion.models import Version

from importer_publikacji.wzbogacanie import zrodla
from importer_publikacji.wzbogacanie.pola import BRAK_W_BPP, ROZNE, ZGODNE, porownaj
from pbn_api.models import Institution, Publication, PublikacjaInstytucji, Scientist

pytestmark = pytest.mark.django_db

UID = "5e709189878c28a04737dc6f"
HASH_1 = "11111111-1111-4111-8111-111111111111"
HASH_2 = "22222222-2222-4222-8222-222222222222"
HASH_3 = "33333333-3333-4333-8333-333333333333"


def _wersja(identyfikator, data, biezaca=False, **pola):
    obiekt = {
        "title": "Dobry tytuł pracy",
        "year": 2023,
        "type": "ARTICLE",
        "volume": "7",
        "issue": "2",
        "pagesFromTo": "10-20",
        "doi": "10.1234/abc",
        "mainLanguage": "pol",
        "journal": {"title": "Czasopismo", "issn": "1234-5678"},
        "authors": {
            "5e7093d7878c28a0473b1ac0": {"lastName": "Kowalski", "name": "Jan"}
        },
    }
    obiekt.update(pola)
    return {
        "current": biezaca,
        "createdTime": data,
        "versionHash": identyfikator,
        "object": obiekt,
    }


WERSJE = [
    _wersja(HASH_1, "2023-01-10T10:00:00.000+00:00"),
    _wersja(HASH_2, "2023-06-15T12:30:00.000+00:00", pagesFromTo="10-25"),
    _wersja(
        HASH_3,
        "2024-03-01T09:00:00.000+00:00",
        biezaca=True,
        title="Zepsuty tytuł",
        volume="99",
    ),
]


@pytest.fixture
def publikacja_pbn():
    return Publication.objects.create(
        mongoId=UID, status="ACTIVE", versions=copy.deepcopy(WERSJE)
    )


@pytest.fixture
def rekord(wydawnictwo_ciagle, publikacja_pbn, uczelnia):
    """Rekord „zepsuty” — odpowiada najnowszej wersji z PBN."""
    w = wydawnictwo_ciagle
    w.tytul_oryginalny = "Zepsuty tytuł"
    w.rok = 2023
    w.tom = "99"
    w.nr_zeszytu = "2"
    w.strony = "10-20"
    w.doi = "10.1234/abc"
    w.issn = "1234-5678"
    w.pbn_uid = publikacja_pbn
    w.save()
    return w


@pytest.fixture
def bez_dostepu_do_pbn(mocker):
    """Każda próba połączenia z PBN wywraca test — widoki mają pracować na
    lokalnej kopii (odświeża ją tylko przycisk „Odśwież z PBN”)."""
    return mocker.patch.object(
        zrodla,
        "_klient_pbn_bez_ponowien",
        side_effect=AssertionError("widok nie może łączyć się z PBN"),
    )


def _przypnij(uczelnia, publikacja_pbn, identyfikator):
    uczelnia.pbn_uid = baker.make(Institution)
    uczelnia.save()
    PublikacjaInstytucji.objects.create(
        insPersonId=baker.make(Scientist),
        institutionId=uczelnia.pbn_uid,
        publicationId=publikacja_pbn,
        publicationVersion=identyfikator,
    )


def _zid(wersja):
    """Wartość ukrytego pola formularza: publikacja i wersja z podglądu."""
    return f"pbn:{UID}:{wersja}"


def _url(rekord, wersja=""):
    url = reverse("admin:bpp_wydawnictwo_ciagle_wzbogac", args=(rekord.pk, "pbn"))
    return f"{url}?wersja={wersja}" if wersja else url


def test_lista_wersji_od_najnowszej_z_oznaczeniami(rekord, uczelnia, publikacja_pbn):
    _przypnij(uczelnia, publikacja_pbn, HASH_2)

    wersje = zrodla.wersje_pbn(publikacja_pbn, uczelnia)

    assert [w.identyfikator for w in wersje] == [HASH_3, HASH_2, HASH_1]
    assert [w.biezaca for w in wersje] == [True, False, False]
    assert [w.przypieta for w in wersje] == [False, True, False]
    assert wersje[1].oznaczenia == ["przypięta na profilu instytucji"]
    assert "15.06.2023" in wersje[1].data_tekst


def test_domyslnie_najnowsza_gdy_profil_nie_wskazuje_wersji(rekord, uczelnia):
    dane = zrodla.pobierz_z_pbn(rekord, uczelnia)

    assert dane.wersja.identyfikator == HASH_3
    assert not dane.wczesniejsza_wersja
    assert dane.ostrzezenia == []
    assert dane.publikacja.title == "Zepsuty tytuł"


def test_domyslnie_przypieta_i_ostrzezenie_o_rozbieznosci(
    rekord, uczelnia, publikacja_pbn
):
    _przypnij(uczelnia, publikacja_pbn, HASH_2)

    dane = zrodla.pobierz_z_pbn(rekord, uczelnia)

    assert dane.wersja.identyfikator == HASH_2
    assert len(dane.ostrzezenia) == 1
    assert "przypięta jest wersja z 15.06.2023" in dane.ostrzezenia[0]
    assert "najnowsza w repozytorium PBN jest z 01.03.2024" in dane.ostrzezenia[0]


def test_porownanie_z_wczesniejsza_wersja(rekord, uczelnia):
    dane = zrodla.pobierz_z_pbn(rekord, uczelnia, wersja=HASH_1)

    assert dane.wczesniejsza_wersja
    w = {x.klucz: x for x in porownaj(rekord, dane.publikacja)}
    assert w["tytul_oryginalny"].status == ROZNE
    assert w["tom"].status == ROZNE
    assert w["strony"].status == ZGODNE
    assert w["doi"].status == ZGODNE


def test_nieznana_wersja(rekord, uczelnia):
    dane = zrodla.pobierz_z_pbn(rekord, uczelnia, wersja="nie-ma")

    assert dane.publikacja is None
    assert "Nie ma już takiej wersji" in dane.blad
    # Lista wersji zostaje — redaktor wybiera inną.
    assert len(dane.wersje) == 3


def test_widok_pokazuje_liste_wersji(admin_client, rekord, bez_dostepu_do_pbn):
    res = admin_client.get(_url(rekord))

    tresc = res.content.decode()
    assert "Wersje tej publikacji w PBN" in tresc
    for data in ("10.01.2023", "15.06.2023", "01.03.2024"):
        assert data in tresc
    assert f"wersja={HASH_1}" in tresc
    assert "najnowsza w PBN" in tresc
    # Podgląd nie łączy się z PBN: pokazuje lokalną kopię, z datą
    # i przyciskiem odświeżenia.
    assert "Dane z lokalnej kopii PBN z" in tresc
    assert "Odśwież z PBN" in tresc
    # Rekord odpowiada najnowszej wersji.
    assert "Wszystko się zgadza" in tresc


def test_widok_odtwarza_pola_ze_starszej_wersji_i_zapisuje_historie(
    admin_client, admin_user, rekord, uczelnia, bez_dostepu_do_pbn
):
    dane = zrodla.pobierz_z_pbn(rekord, uczelnia, wersja=HASH_1)
    w = {x.klucz: x for x in porownaj(rekord, dane.publikacja)}

    res = admin_client.post(
        _url(rekord),
        {
            "wersja": HASH_1,
            "zrodlo_id": _zid(HASH_1),
            "pole": [w["tytul_oryginalny"].wartosc_wyboru],
        },
        follow=True,
    )

    assert res.status_code == 200
    rekord.refresh_from_db()
    assert rekord.tytul_oryginalny == "Dobry tytuł pracy"
    # Tom też się różnił, ale nie był zaznaczony.
    assert rekord.tom == "99"
    opis = "Odtworzono z PBN, wersja z dnia 10.01.2023, 11:00: pola Tytuł oryginalny"
    wpis = LogEntry.objects.get(object_id=str(rekord.pk), action_flag=CHANGE)
    assert wpis.change_message == opis
    assert wpis.user == admin_user
    najnowsza = Version.objects.get_for_object(rekord).first()
    assert najnowsza.revision.comment == opis
    # Po zatwierdzeniu wracamy do porównania z tą samą wersją.
    assert res.redirect_chain[-1][0].endswith(f"?wersja={HASH_1}")


def test_wzbogacenie_z_najnowszej_wersji_ma_opis_wzbogacono(
    admin_client, rekord, bez_dostepu_do_pbn
):
    rekord.nr_zeszytu = ""
    rekord.save()
    dane = zrodla.pobierz_z_pbn(rekord, None)
    w = {x.klucz: x for x in porownaj(rekord, dane.publikacja)}
    assert w["nr_zeszytu"].status == BRAK_W_BPP

    admin_client.post(
        _url(rekord),
        {
            "wersja": HASH_3,
            "zrodlo_id": _zid(HASH_3),
            "pole": [w["nr_zeszytu"].wartosc_wyboru],
        },
    )

    rekord.refresh_from_db()
    assert rekord.nr_zeszytu == "2"
    wpis = LogEntry.objects.get(object_id=str(rekord.pk), action_flag=CHANGE)
    assert wpis.change_message == (
        "Wzbogacono z PBN (wersja z 01.03.2024, 10:00 (najnowsza w PBN)): "
        "pola Nr zeszytu"
    )


def _klient_pbn(mocker, **konfiguracja):
    client = MagicMock(spec=["get_publication_by_id"])
    client.get_publication_by_id.configure_mock(**konfiguracja)
    mocker.patch.object(zrodla, "_klient_pbn_bez_ponowien", return_value=client)
    return client


def test_odswiez_z_pbn_pobiera_nowe_wersje_tylko_odczytem(
    admin_client, rekord, publikacja_pbn, mocker
):
    """„Odśwież z PBN” pobiera publikację z PBN (jedyne dozwolone wywołanie)
    i zapisuje nowe wersje w lokalnej kopii; do PBN nic nie jest wysyłane.
    Samo otwarcie podglądu z PBN się nie łączy."""
    nowa = _wersja("44444444-4444-4444-8444-444444444444", "2024-09-09T08:00:00+00:00")
    client = _klient_pbn(
        mocker,
        return_value={
            "mongoId": UID,
            "status": "ACTIVE",
            "verificationLevel": "VERIFIED",
            "verified": True,
            "versions": [*copy.deepcopy(WERSJE), nowa],
        },
    )

    assert "09.09.2024" not in admin_client.get(_url(rekord)).content.decode()
    client.get_publication_by_id.assert_not_called()

    res = admin_client.post(_url(rekord), {"odswiez": "1"}, follow=True)

    client.get_publication_by_id.assert_called_once_with(UID)
    tresc = res.content.decode()
    assert "Pobrano aktualne dane z PBN" in tresc
    assert "09.09.2024" in tresc
    publikacja_pbn.refresh_from_db()
    assert len(publikacja_pbn.versions) == 4


def test_zatwierdzenie_nie_laczy_sie_z_pbn(
    admin_client, rekord, uczelnia, bez_dostepu_do_pbn
):
    """Zatwierdzamy to, co było na podglądzie — z lokalnej kopii."""
    dane = zrodla.pobierz_z_pbn(rekord, uczelnia, wersja=HASH_1)
    w = {x.klucz: x for x in porownaj(rekord, dane.publikacja)}

    admin_client.post(
        _url(rekord),
        {
            "wersja": HASH_1,
            "zrodlo_id": _zid(HASH_1),
            "pole": [w["tom"].wartosc_wyboru],
        },
    )

    bez_dostepu_do_pbn.assert_not_called()
    rekord.refresh_from_db()
    assert rekord.tom == "7"


def test_blad_pbn_przy_odswiezaniu_zostawia_lokalna_kopie(
    admin_client, rekord, publikacja_pbn, mocker
):
    from pbn_api.exceptions import HttpException

    _klient_pbn(mocker, side_effect=HttpException(500, "/x", "awaria"))

    res = admin_client.post(_url(rekord), {"odswiez": "1"}, follow=True)

    assert res.status_code == 200
    tresc = res.content.decode()
    assert "Nie udało się pobrać aktualnych danych z PBN" in tresc
    assert "Pokazuję dane pobrane wcześniej" in tresc
    assert "Wersje tej publikacji w PBN" in tresc
    publikacja_pbn.refresh_from_db()
    assert len(publikacja_pbn.versions) == 3


def test_niedostepny_pbn_nie_wiesza_widoku(admin_client, rekord, uczelnia, mocker):
    """Zwykły transport PBN ponawia błędy połączenia kilkanaście razy
    z przerwami (minuty). Podgląd nie łączy się z PBN wcale, a „Odśwież
    z PBN” wysyła JEDNO zapytanie z krótkim limitem czasu."""
    import requests

    uczelnia.pbn_app_name = "aplikacja"
    uczelnia.pbn_app_token = "token"
    uczelnia.pbn_api_root = "https://pbn.example"
    uczelnia.save()
    get = mocker.patch.object(
        zrodla.requests, "get", side_effect=requests.ConnectTimeout("brak sieci")
    )
    czekanie = mocker.patch("time.sleep")

    res = admin_client.get(_url(rekord))

    assert res.status_code == 200
    assert "Wersje tej publikacji w PBN" in res.content.decode()
    get.assert_not_called()

    res = admin_client.post(_url(rekord), {"odswiez": "1"}, follow=True)

    assert res.status_code == 200
    assert "Nie udało się pobrać aktualnych danych z PBN" in res.content.decode()
    assert get.call_count == 1
    assert get.call_args.kwargs["timeout"] == zrodla.LIMIT_CZASU_PBN
    czekanie.assert_not_called()


def test_odswiez_bez_konfiguracji_pbn(admin_client, rekord):
    res = admin_client.post(_url(rekord), {"odswiez": "1"}, follow=True)

    assert "Uczelnia nie ma skonfigurowanego dostępu do PBN" in res.content.decode()


# --- Słowa kluczowe z PBN: osobno polskie i angielskie ----------------------


def _z_slowami(publikacja_pbn, slowa):
    wersje = copy.deepcopy(WERSJE)
    wersje[-1]["object"]["keywords"] = slowa
    publikacja_pbn.versions = wersje
    publikacja_pbn.save()


def _slowa(rekord, uczelnia):
    dane = zrodla.pobierz_z_pbn(rekord, uczelnia)
    return {
        x.klucz: x
        for x in porownaj(rekord, dane.publikacja)
        if x.klucz.startswith("slowa")
    }


def test_slowa_kluczowe_zgodne_gdy_kazdy_jezyk_w_swoim_polu(
    rekord, uczelnia, publikacja_pbn
):
    """PBN podaje słowa polskie i angielskie razem; BPP trzyma angielskie
    w osobnym polu — poprawny rekord jest „zgodny”."""
    _z_slowami(publikacja_pbn, {"pol": ["chemia", "Kryształy"], "eng": ["crystals"]})
    rekord.slowa_kluczowe.set(["kryształy", "chemia"])
    rekord.slowa_kluczowe_eng = ["Crystals"]
    rekord.save()

    w = _slowa(rekord, uczelnia)

    assert w["slowa_kluczowe"].status == ZGODNE
    assert w["slowa_kluczowe_eng"].status == ZGODNE


def test_przeniesienie_slow_dopisuje_brakujace_w_polu_swojego_jezyka(
    admin_client, rekord, uczelnia, publikacja_pbn
):
    _z_slowami(publikacja_pbn, {"pol": ["chemia", "kryształy"], "eng": ["crystals"]})
    rekord.slowa_kluczowe.set(["chemia", "dopisane ręcznie"])
    rekord.slowa_kluczowe_eng = ["manual"]
    rekord.save()
    w = _slowa(rekord, uczelnia)
    assert w["slowa_kluczowe"].status == ROZNE
    assert w["slowa_kluczowe_eng"].status == ROZNE
    assert "kryształy" in w["slowa_kluczowe"].zmiana
    assert "chemia" not in w["slowa_kluczowe"].zmiana

    admin_client.post(
        _url(rekord),
        {
            "wersja": HASH_3,
            "zrodlo_id": _zid(HASH_3),
            "pole": [
                w["slowa_kluczowe"].wartosc_wyboru,
                w["slowa_kluczowe_eng"].wartosc_wyboru,
            ],
        },
    )

    rekord.refresh_from_db()
    # Angielskie nie trafiają do pola języka głównego, a słowa dopisane
    # ręcznie zostają.
    assert sorted(rekord.slowa_kluczowe.names()) == [
        "chemia",
        "dopisane ręcznie",
        "kryształy",
    ]
    assert rekord.slowa_kluczowe_eng == ["manual", "crystals"]
    # Rekord ma teraz wszystko ze źródła (i własne słowa) — nie ma czego
    # przenosić.
    po = _slowa(rekord, uczelnia)
    assert not po["slowa_kluczowe"].mozna_przeniesc
    assert not po["slowa_kluczowe_eng"].mozna_przeniesc


def test_slowa_podane_jednym_ciagiem_sa_dzielone(rekord, uczelnia, publikacja_pbn):
    """PBN często podaje wszystkie słowa jednym ciągiem — dzielimy jak
    import z PBN."""
    _z_slowami(publikacja_pbn, {"pol": ["chemia; kryształy ;sól"], "eng": "a, b"})

    w = _slowa(rekord, uczelnia)

    assert w["slowa_kluczowe"].zrodlo == "chemia, kryształy, sól"
    assert w["slowa_kluczowe_eng"].zrodlo == "a, b"
    assert w["slowa_kluczowe"].mozna_przeniesc


def test_za_dlugie_slowo_kluczowe_nie_jest_przenoszone(
    admin_client, rekord, uczelnia, publikacja_pbn
):
    """Słowo dłuższe niż 100 znaków nie mieści się w BPP — pole nie daje się
    zaznaczyć, a wymuszone zatwierdzenie niczego nie zapisuje (bez błędu 500)."""
    _z_slowami(publikacja_pbn, {"pol": ["bardzo długie słowo kluczowe " * 6]})
    w = _slowa(rekord, uczelnia)["slowa_kluczowe"]
    assert not w.mozna_przeniesc
    assert "najwyżej 100 znaków" in w.uwaga

    res = admin_client.post(
        _url(rekord),
        {"wersja": HASH_3, "zrodlo_id": _zid(HASH_3), "pole": [w.wartosc_wyboru]},
        follow=True,
    )

    assert res.status_code == 200
    assert not rekord.slowa_kluczowe.exists()


def test_e_issn_z_bpp_podany_w_pbn_jako_issn_nie_jest_brakiem(rekord, uczelnia):
    """PBN podaje jeden numer (jako ISSN), BPP ma go w polu e-ISSN — żadne
    z dwóch pól nie jest wtedy „różne” ani „brakujące”."""
    rekord.issn = ""
    rekord.e_issn = "1234-5678"
    rekord.save()
    dane = zrodla.pobierz_z_pbn(rekord, uczelnia)

    w = {x.klucz: x for x in porownaj(rekord, dane.publikacja)}

    assert w["issn"].status == ZGODNE
    assert w["e_issn"].status == ZGODNE
    assert "ISSN" in w["e_issn"].uwaga


def test_issn_z_obiektu_publikacji_pbn():
    """ISSN bywa w PBN wprost przy publikacji (książka w serii), nie przy
    czasopiśmie."""
    from importer_publikacji.providers.pbn import publikacja_z_obiektu_wersji

    obiekt = {"title": "Książka", "type": "BOOK", "issn": "1111-2222"}

    assert publikacja_z_obiektu_wersji({}, obiekt, UID).issn == "1111-2222"
    obiekt["journal"] = {"issn": "3333-4444"}
    assert publikacja_z_obiektu_wersji({}, obiekt, UID).issn == "1111-2222"
    del obiekt["issn"]
    assert publikacja_z_obiektu_wersji({}, obiekt, UID).issn == "3333-4444"


# --- Druga recenzja ---------------------------------------------------------


def test_zatwierdzenie_odrzucone_gdy_zmienil_sie_odpowiednik_pbn(
    admin_client, rekord, uczelnia, bez_dostepu_do_pbn
):
    """Między podglądem a zatwierdzeniem rekord dostał inny odpowiednik
    w PBN — dane z podglądu dotyczą poprzedniej publikacji, nic nie zapisujemy."""
    dane = zrodla.pobierz_z_pbn(rekord, uczelnia, wersja=HASH_1)
    w = {x.klucz: x for x in porownaj(rekord, dane.publikacja)}
    inna = Publication.objects.create(
        mongoId="b" * 24, status="ACTIVE", versions=copy.deepcopy(WERSJE)
    )
    type(rekord).objects.filter(pk=rekord.pk).update(pbn_uid=inna)

    res = admin_client.post(
        _url(rekord),
        {
            "wersja": HASH_1,
            "zrodlo_id": _zid(HASH_1),
            "pole": [w["tom"].wartosc_wyboru],
        },
        follow=True,
    )

    assert "Nic nie zmieniono" in res.content.decode()
    rekord.refresh_from_db()
    assert rekord.tom == "99"
    assert not LogEntry.objects.filter(object_id=str(rekord.pk)).exists()


def test_streszczenia_wszystkie_jezyki_z_pbn(rekord, uczelnia, publikacja_pbn, jezyki):
    """PBN ma streszczenie polskie (zgodne z BPP) i angielskie (w BPP go nie
    ma) — brak angielskiego nie jest gubiony."""
    from bpp.models import Jezyk

    wersje = copy.deepcopy(WERSJE)
    wersje[-1]["object"]["abstracts"] = {
        "pol": "Streszczenie po polsku.",
        "eng": "An abstract in English.",
    }
    publikacja_pbn.versions = wersje
    publikacja_pbn.save()
    polski = Jezyk.objects.get(skrot="pol.")
    angielski = Jezyk.objects.get(skrot="ang.")
    angielski.pbn_uid = baker.make("pbn_api.Language", code="eng")
    angielski.save()
    rekord.streszczenia.create(
        streszczenie="Streszczenie po polsku.", jezyk_streszczenia=polski
    )

    dane = zrodla.pobierz_z_pbn(rekord, uczelnia)
    w = [x for x in porownaj(rekord, dane.publikacja) if "streszczenie" in x.klucz]

    w.sort(key=lambda x: x.etykieta, reverse=True)
    assert [(x.etykieta, x.status) for x in w] == [
        ("Streszczenie (polski)", ZGODNE),
        ("Streszczenie (angielski)", BRAK_W_BPP),
    ]
    w[1].zastosuj(rekord)
    nowe = rekord.streszczenia.get(streszczenie="An abstract in English.")
    assert nowe.jezyk_streszczenia == angielski
    # Inne streszczenie w tym samym języku to „różne”, nie „brak”.
    rekord.streszczenia.filter(pk=nowe.pk).update(streszczenie="Another abstract.")
    w = [x for x in porownaj(rekord, dane.publikacja) if "angielski" in x.etykieta]
    assert w[0].status == ROZNE
    assert w[0].bpp == "Another abstract."
