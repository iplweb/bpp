"""Zadanie w tle, komenda, wybór wersji, strażnicy dotychczasowych funkcji."""

import pytest
from django.core.management import call_command
from django.utils import timezone
from model_bakery import baker

from bpp.models import Uczelnia, Wydawnictwo_Zwarte
from pbn_api.models import Publication
from pbn_integrator import importer
from pbn_uzgadnianie import silnik, tasks
from pbn_uzgadnianie.models import UzgodnienieZPBN
from pbn_uzgadnianie.wersje import (
    BIEZACA_BRAK_PRZYPIETEJ,
    BIEZACA_NIEJEDNOZNACZNA,
    BIEZACA_NIEZNANA_PRZYPIETA,
    PRZYPIETA,
    wybierz_wersje,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def z_tokenem(przebieg):
    def zrob(**pola):
        p = przebieg(**pola)
        p.user.pbn_token = "token"
        p.user.pbn_token_updated = timezone.now()
        p.user.save()
        return p

    return zrob


@pytest.fixture
def klient_uczelni(klient, mocker):
    mocker.patch.object(Uczelnia, "pbn_client", lambda self, token: klient)
    return klient


def test_zadanie_wykonuje_przebieg(klient_uczelni, ksiazka_pbn, z_tokenem):
    klient_uczelni.dodaj("pbn-nowa", ksiazka_pbn("Monografia z zadania w tle"))
    p = z_tokenem()

    tasks.uzgodnij_z_pbn(p.pk)

    p.refresh_from_db()
    assert p.status == "zakonczone" and p.postep == 100
    assert p.podsumowanie[silnik.UTWORZONO] == 1
    assert Wydawnictwo_Zwarte.objects.filter(pbn_uid_id="pbn-nowa").exists()


def test_zadanie_doreczone_drugi_raz_nie_zaczyna_od_nowa(klient_uczelni, z_tokenem):
    p = z_tokenem(status="zakonczone")

    tasks.uzgodnij_z_pbn(p.pk)

    assert klient_uczelni.wywolania == []


def test_blad_przebiegu_zamyka_go_jako_bledny_i_idzie_dalej(przebieg, mocker):
    """Bez ważnej autoryzacji PBN: przebieg kończy jako „błąd” (nie wisi jako
    aktywny), a wyjątek trafia do logu i jest propagowany."""
    p = przebieg()
    log = mocker.patch.object(tasks.logger, "exception")

    with pytest.raises(ValueError, match="PBN"):
        tasks.uzgodnij_z_pbn(p.pk)

    p.refresh_from_db()
    assert p.status == "blad"
    assert "ValueError" in p.blad
    log.assert_called_once()


def test_nadzorca_bazy_zapisuje_postep_osobnym_polaczeniem(przebieg):
    """Zapytania nadzorcy muszą pasować do tabeli modelu. (W teście wiersz
    żyje w niezatwierdzonej transakcji, więc osobne połączenie go nie widzi —
    sprawdzamy poprawność SQL i to, że brak wiersza nie jest anulowaniem.)"""
    nadzorca = silnik.NadzorcaBazy(przebieg().pk)
    try:
        nadzorca.etap("Etap testowy", 150)
        nadzorca.sprawdz_anulowanie()
    finally:
        nadzorca.zamknij()


def test_komenda_bez_danych_mowi_co_zrobic(klient_uczelni, z_tokenem):
    from django.core.management.base import CommandError

    user = z_tokenem(status="zakonczone").user

    with pytest.raises(CommandError, match="--pobierz"):
        call_command(
            "pbn_uzgodnij", "--rok-od=2026", "--rok-do=2026", f"--uzytkownik={user}"
        )

    assert klient_uczelni.wywolania == []


def test_komenda_pobierz_dry_run_i_wykonanie_na_pobranych(
    klient_uczelni, ksiazka_pbn, z_tokenem, tmp_path, capsys
):
    klient_uczelni.dodaj("pbn-nowa", ksiazka_pbn("Monografia z linii poleceń"))
    user = z_tokenem(status="zakonczone").user
    argumenty = ["--rok-od=2026", "--rok-do=2026", f"--uzytkownik={user.username}"]
    plik = tmp_path / "raport.xlsx"

    call_command("pbn_uzgodnij", *argumenty, "--pobierz", "--dry-run", f"--xlsx={plik}")

    assert not Wydawnictwo_Zwarte.objects.exists()
    assert UzgodnienieZPBN.objects.filter(tryb="pobranie", status="zakonczone").exists()
    assert UzgodnienieZPBN.objects.filter(tryb="podglad", status="zakonczone").exists()
    assert plik.stat().st_size > 0
    wyjscie = capsys.readouterr().out
    assert "profil instytucji" in wyjscie and "pobrane dzisiaj" in wyjscie

    # Drugie wywołanie pracuje na pobranych danych — PBN nie jest odpytywany.
    klient_uczelni.wywolania.clear()
    call_command("pbn_uzgodnij", *argumenty)

    assert klient_uczelni.wywolania == []
    assert Wydawnictwo_Zwarte.objects.filter(pbn_uid_id="pbn-nowa").exists()


def test_pobranie_zapisuje_date_kazdego_zrodla_i_nic_nie_zmienia_w_bpp(
    klient_uczelni, ksiazka_pbn, z_tokenem
):
    from pbn_uzgadnianie.swiezosc import stan_danych

    klient_uczelni.dodaj("pbn-nowa", ksiazka_pbn("Monografia tylko pobrana"))
    p = z_tokenem(tryb="pobranie")

    tasks.uzgodnij_z_pbn(p.pk)

    p.refresh_from_db()
    assert p.status == "zakonczone" and p.wynik == []
    assert not Wydawnictwo_Zwarte.objects.exists()
    stan = stan_danych(p.zakres)
    assert [z["klucz"] for z in stan["zrodla"]] == [
        "profil",
        "publikacje",
        "oswiadczenia",
        "wyszukiwanie",
    ]
    assert stan["stare"] is False and stan["lata"] == (2026, 2026)


def test_uzgadnianie_na_pobranych_danych_dla_wezszych_lat(
    klient_uczelni, ksiazka_pbn, z_tokenem
):
    """Dane pobrane dla 2025–2026, uzgadnianie tylko 2026: bez pobierania
    i tylko prace z 2026."""
    klient_uczelni.dodaj("pbn-2025", ksiazka_pbn("Monografia z 2025", rok=2025))
    klient_uczelni.dodaj("pbn-2026", ksiazka_pbn("Monografia z 2026", rok=2026))
    pobranie = z_tokenem(tryb="pobranie", rok_od=2025, rok_do=2026)
    tasks.uzgodnij_z_pbn(pobranie.pk)
    pobranie.refresh_from_db()
    klient_uczelni.wywolania.clear()
    p = z_tokenem(rok_od=2026, rok_do=2026, na_podstawie=pobranie)
    UzgodnienieZPBN.objects.filter(pk=p.pk).update(user=pobranie.user)

    tasks.uzgodnij_z_pbn(p.pk)

    assert klient_uczelni.wywolania == []
    assert Wydawnictwo_Zwarte.objects.filter(pbn_uid_id="pbn-2026").exists()
    assert not Wydawnictwo_Zwarte.objects.filter(pbn_uid_id="pbn-2025").exists()


def test_opis_daty():
    import datetime

    from pbn_uzgadnianie.swiezosc import opis_daty

    teraz = timezone.make_aware(datetime.datetime(2026, 11, 23, 9, 0))
    wczoraj = timezone.make_aware(datetime.datetime(2026, 11, 22, 14, 10))

    assert opis_daty(wczoraj, teraz) == "wczoraj, 22.11.2026 14:10"
    assert opis_daty(teraz, teraz) == "dzisiaj, 23.11.2026 09:00"
    assert opis_daty(wczoraj - datetime.timedelta(days=4), teraz).startswith(
        "5 dni temu"
    )


# -- wybór wersji ---------------------------------------------------------------


def _publikacja(*wersje):
    return Publication(mongoId="x", versions=list(wersje))


def test_wybor_wersji():
    stara = {"versionHash": "AAA", "object": {"title": "stara"}}
    nowa = {"versionHash": "bbb", "current": True, "object": {"title": "nowa"}}
    pub = _publikacja(stara, nowa)

    przypieta = wybierz_wersje(pub, ["aaa", "aaa"])
    assert (przypieta.wersja, przypieta.zrodlo) == (stara, PRZYPIETA)
    assert przypieta.jest_nowsza_biezaca is True

    ta_sama = wybierz_wersje(pub, ["bbb"])
    assert (ta_sama.wersja, ta_sama.jest_nowsza_biezaca) == (nowa, False)

    assert wybierz_wersje(pub, []).zrodlo == BIEZACA_BRAK_PRZYPIETEJ
    assert wybierz_wersje(pub, [None]).wersja is nowa
    assert wybierz_wersje(pub, ["zzz"]).zrodlo == BIEZACA_NIEZNANA_PRZYPIETA
    assert wybierz_wersje(pub, ["aaa", "bbb"]).zrodlo == BIEZACA_NIEJEDNOZNACZNA
    assert wybierz_wersje(_publikacja(), ["aaa"]).obiekt is None


# -- strażnicy: dotychczasowy import z PBN działa jak dotąd ------------------------


def _ksiazka_dwie_wersje(slowniki):
    return baker.make(
        Publication,
        mongoId="pbn-straznik",
        status="ACTIVE",
        versions=[
            {
                "versionHash": "stara",
                "object": {"type": "BOOK", "title": "Wersja starsza", "year": 2020},
            },
            {
                "current": True,
                "versionHash": "biezaca",
                "object": {"type": "BOOK", "title": "Wersja bieżąca", "year": 2020},
            },
        ],
    )


def test_straznik_import_z_pbn_nadal_bierze_wersje_biezaca(slowniki):
    """Poza blokiem ``importuj_z_wersji`` importer zachowuje się jak dotąd."""
    _ksiazka_dwie_wersje(slowniki)

    rekord = importer.importuj_publikacje_po_pbn_uid_id(
        "pbn-straznik", client=None, default_jednostka=None
    )

    assert rekord.tytul_oryginalny == "Wersja bieżąca"


def test_wybieracz_wersji_dziala_tylko_w_bloku(slowniki):
    from pbn_integrator.importer.helpers import importuj_z_wersji, wersja_do_importu

    pub = _ksiazka_dwie_wersje(slowniki)

    with importuj_z_wersji(lambda p: p.versions[0]):
        assert wersja_do_importu(pub)["versionHash"] == "stara"
    with importuj_z_wersji(lambda p: None):
        assert wersja_do_importu(pub)["versionHash"] == "biezaca"
    assert wersja_do_importu(pub)["versionHash"] == "biezaca"


def test_straznik_import_masowy_nadal_importuje_cala_kopie(slowniki):
    """„Import z PBN” (masowy) dalej bierze całą lokalną kopię — bez filtra
    profilu instytucji. Uzgadnianie tego nie zmienia."""
    from bpp.models import Rodzaj_Zrodla

    Rodzaj_Zrodla.objects.get_or_create(nazwa="periodyk")
    _ksiazka_dwie_wersje(slowniki)

    importer.importuj_publikacje_instytucji(client=None, default_jednostka=None)

    assert Wydawnictwo_Zwarte.objects.filter(pbn_uid_id="pbn-straznik").exists()
