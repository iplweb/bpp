"""Bezpiecznik „lokalna kopia produkcji" — kolejka i automaty wysyłki do PBN."""

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import CommandError, call_command
from django.db import connection
from model_bakery import baker

from bpp.models.profile import BppUser
from pbn_api.autoryzacja import zapisz_token
from pbn_export_queue import bezpiecznik, operacje, tasks
from pbn_export_queue.models import PBN_Export_Queue

KOMENDA = "pbn_bezpiecznik_lokalnej_kopii"
WYSLIJ = "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay"
SEND_TO_PBN = "pbn_export_queue.models.PBN_Export_Queue.send_to_pbn"


@pytest.fixture
def lokalna(settings):
    """Instancja spełniająca kryteria „lokalnej" (DEBUG + baza na tej maszynie)."""
    settings.DEBUG = True
    # W CI baza jest pod nazwą serwisu compose, lokalnie pod gniazdem — test
    # nie może zależeć od tego, gdzie akurat stoi baza testowa.
    with patch("pbn_export_queue.bezpiecznik.host_bazy", return_value="localhost"):
        yield settings


@pytest.fixture
def redaktor():
    return baker.make(BppUser, username="redaktor", is_active=True)


def _wpis(user, rekord, **kw):
    return baker.make(PBN_Export_Queue, zamowil=user, rekord_do_wysylki=rekord, **kw)


def _uruchom(*args, **kw):
    out = StringIO()
    call_command(KOMENDA, *args, stdout=out, **kw)
    return out.getvalue()


# --- odmowa na instancji, która nie wygląda na lokalną ----------------------


@pytest.mark.django_db
def test_odmowa_gdy_debug_wylaczony(settings, redaktor, wydawnictwo_ciagle):
    settings.DEBUG = False
    wpis = _wpis(redaktor, wydawnictwo_ciagle)

    with pytest.raises(CommandError, match="ODMOWA.*DEBUG"):
        _uruchom("--tak-to-jest-lokalna-kopia")

    wpis.refresh_from_db()
    assert wpis.wysylke_zakonczono is None


@pytest.mark.django_db
def test_odmowa_gdy_baza_na_innym_hoscie(lokalna, redaktor, wydawnictwo_ciagle):
    wpis = _wpis(redaktor, wydawnictwo_ciagle)

    with patch("pbn_export_queue.bezpiecznik.host_bazy", return_value="dbserver"):
        with pytest.raises(CommandError, match="ODMOWA.*dbserver"):
            _uruchom("--tak-to-jest-lokalna-kopia")

    wpis.refresh_from_db()
    assert wpis.wysylke_zakonczono is None


@pytest.mark.django_db
def test_odmowa_bez_flagi(lokalna, redaktor, wydawnictwo_ciagle):
    wpis = _wpis(redaktor, wydawnictwo_ciagle)

    with pytest.raises(CommandError, match="--tak-to-jest-lokalna-kopia"):
        _uruchom()

    wpis.refresh_from_db()
    assert wpis.wysylke_zakonczono is None


@pytest.mark.django_db
def test_flaga_nie_obchodzi_kryteriow(settings):
    """Sama flaga nie wystarcza — kryteria lokalności są twarde."""
    settings.DEBUG = False
    with pytest.raises(CommandError, match="ODMOWA"):
        _uruchom("--tak-to-jest-lokalna-kopia", "--lokalny-host-bazy", "dbserver")


@pytest.mark.parametrize(
    "host,lokalny",
    [
        ("", True),
        ("localhost", True),
        ("127.0.0.1", True),
        ("/tmp/tcpg-abc", True),
        ("dbserver", False),
        ("10.0.0.5", False),
        ("baza.example.org", False),
    ],
)
def test_kryterium_hosta_bazy(settings, host, lokalny):
    settings.DEBUG = True
    with patch.dict(connection.settings_dict, {"HOST": host}):
        assert (bezpiecznik.powody_nielokalnosci() == []) is lokalny


def test_dodatkowy_lokalny_host_bazy(settings):
    settings.DEBUG = True
    with patch.dict(connection.settings_dict, {"HOST": "db"}):
        assert bezpiecznik.powody_nielokalnosci() != []
        assert bezpiecznik.powody_nielokalnosci(["db"]) == []


# --- kolejka -----------------------------------------------------------------


@pytest.mark.django_db
def test_zamyka_niezakonczone_wpisy(
    lokalna, redaktor, wydawnictwo_ciagle, wydawnictwo_zwarte, patent
):
    czeka = _wpis(redaktor, wydawnictwo_ciagle, komunikat="stary komunikat")
    na_logowanie = _wpis(redaktor, wydawnictwo_zwarte, retry_after_user_authorised=True)
    wycofanie = _wpis(redaktor, patent, operacja=PBN_Export_Queue.Operacja.WYCOFANIE)

    out = _uruchom("--tak-to-jest-lokalna-kopia")

    for wpis in (czeka, na_logowanie, wycofanie):
        wpis.refresh_from_db()
        assert wpis.wysylke_zakonczono is not None
        assert wpis.zakonczono_pomyslnie is False
        assert wpis.retry_after_user_authorised is None
        assert wpis.rodzaj_bledu is None
        assert "bezpiecznik lokalnej kopii" in wpis.komunikat
    assert czeka.komunikat.endswith("stary komunikat")
    assert "zamknięto 2 wpis(ów) wysyłki i 1 wpis(ów) wycofania" in out
    assert not PBN_Export_Queue.objects.filter(wysylke_zakonczono=None).exists()


@pytest.mark.django_db
def test_nie_rusza_wpisow_zakonczonych(lokalna, redaktor, wydawnictwo_ciagle):
    from django.utils import timezone

    kiedys = timezone.now() - timezone.timedelta(days=30)
    wyslany = _wpis(
        redaktor,
        wydawnictwo_ciagle,
        wysylke_zakonczono=kiedys,
        zakonczono_pomyslnie=True,
        komunikat="wysłano",
    )

    _uruchom("--tak-to-jest-lokalna-kopia")

    wyslany.refresh_from_db()
    assert wyslany.wysylke_zakonczono == kiedys
    assert wyslany.zakonczono_pomyslnie is True
    assert wyslany.komunikat == "wysłano"


@pytest.mark.django_db
def test_wstrzymany_wpis_mozna_ponowic_recznie(lokalna, redaktor, wydawnictwo_ciagle):
    """Bezpiecznik blokuje automaty, nie funkcję: deweloper ponawia świadomie."""
    wpis = _wpis(redaktor, wydawnictwo_ciagle)
    _uruchom("--tak-to-jest-lokalna-kopia")

    wpis.prepare_for_resend(user=redaktor)

    wpis.refresh_from_db()
    assert wpis.wysylke_zakonczono is None


# --- po zapisaniu tokenu nic nie wychodzi -----------------------------------


@pytest.mark.django_db(transaction=True)
def test_po_bezpieczniku_zapis_tokenu_niczego_nie_wysyla(
    lokalna, redaktor, wydawnictwo_ciagle, wydawnictwo_zwarte
):
    """Sama komenda (bez przełącznika automatów) wystarcza: kolejka z kopii
    produkcji jest zamknięta, więc „ponów po zalogowaniu" nie ma czego wysłać."""
    lokalna.PBN_WSTRZYMAJ_AUTOMATY = False
    _wpis(redaktor, wydawnictwo_ciagle, retry_after_user_authorised=True)
    _wpis(redaktor, wydawnictwo_zwarte, retry_after_user_authorised=True)
    _uruchom("--tak-to-jest-lokalna-kopia")

    with patch(SEND_TO_PBN) as send_to_pbn:
        zapisz_token(redaktor, "prawdziwy-token")

    send_to_pbn.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_kontrola_bez_bezpiecznika_zapis_tokenu_wysyla(
    settings, redaktor, wydawnictwo_ciagle
):
    """Kontrola dla testu wyżej: bez bezpiecznika ten sam zapis tokenu WYSYŁA."""
    from pbn_export_queue.models import SendStatus

    settings.PBN_WSTRZYMAJ_AUTOMATY = False
    _wpis(redaktor, wydawnictwo_ciagle, retry_after_user_authorised=True)

    with patch(SEND_TO_PBN, return_value=SendStatus.FINISHED_ERROR) as send_to_pbn:
        zapisz_token(redaktor, "prawdziwy-token")

    send_to_pbn.assert_called_once()


# --- przełącznik automatów ---------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_przelacznik_wstrzymuje_ponowienie_po_zalogowaniu(
    settings, redaktor, wydawnictwo_ciagle
):
    settings.PBN_WSTRZYMAJ_AUTOMATY = True
    _wpis(redaktor, wydawnictwo_ciagle, retry_after_user_authorised=True)

    with patch(SEND_TO_PBN) as send_to_pbn:
        zapisz_token(redaktor, "prawdziwy-token")

    send_to_pbn.assert_not_called()


@pytest.mark.django_db
def test_przelacznik_wstrzymuje_watchdog(settings, redaktor, wydawnictwo_ciagle):
    _wpis(redaktor, wydawnictwo_ciagle)

    settings.PBN_WSTRZYMAJ_AUTOMATY = True
    with patch(WYSLIJ) as wyslij:
        assert tasks.queue_watchdog() == 0
    wyslij.assert_not_called()

    settings.PBN_WSTRZYMAJ_AUTOMATY = False
    with patch(WYSLIJ) as wyslij:
        assert tasks.queue_watchdog() == 1
    wyslij.assert_called_once()


@pytest.mark.django_db
def test_przelacznik_wstrzymuje_lancuch_nastepny_z_kolejki(
    settings, redaktor, wydawnictwo_ciagle
):
    _wpis(redaktor, wydawnictwo_ciagle)

    settings.PBN_WSTRZYMAJ_AUTOMATY = True
    with patch(WYSLIJ) as wyslij:
        assert tasks.check_and_send_next_in_queue() == 0
    wyslij.assert_not_called()

    settings.PBN_WSTRZYMAJ_AUTOMATY = False
    with patch(WYSLIJ) as wyslij:
        assert tasks.check_and_send_next_in_queue() == 1
    wyslij.assert_called_once()


@pytest.mark.django_db
def test_przelacznik_wstrzymuje_kosz_i_przywrocenie(
    settings, redaktor, wydawnictwo_ciagle, pbn_publication
):
    wydawnictwo_ciagle.pbn_uid = pbn_publication
    wydawnictwo_ciagle.save()

    settings.PBN_WSTRZYMAJ_AUTOMATY = True
    with patch(WYSLIJ) as wyslij:
        assert operacje.zakolejkuj_wycofanie(wydawnictwo_ciagle, redaktor) is None
        assert operacje.zakolejkuj_wysylke(wydawnictwo_ciagle, redaktor) is None
    wyslij.assert_not_called()
    assert not PBN_Export_Queue.objects.exists()

    settings.PBN_WSTRZYMAJ_AUTOMATY = False
    assert operacje.zakolejkuj_wycofanie(wydawnictwo_ciagle, redaktor) is not None


@pytest.mark.django_db
def test_przelacznik_nie_blokuje_recznej_wysylki(
    settings, redaktor, wydawnictwo_ciagle
):
    """Ręczne „wyślij" z kolejki idzie do workera mimo wstrzymanych automatów."""
    settings.PBN_WSTRZYMAJ_AUTOMATY = True
    wpis = _wpis(redaktor, wydawnictwo_ciagle)

    with patch(WYSLIJ) as wyslij:
        wpis.sprobuj_wyslac_do_pbn()

    wyslij.assert_called_once_with(wpis.pk)


def test_komenda_raportuje_stan_przelacznika(db, lokalna):
    lokalna.PBN_WSTRZYMAJ_AUTOMATY = True
    assert "Automaty wysyłki do PBN: WSTRZYMANE" in _uruchom(
        "--tak-to-jest-lokalna-kopia"
    )
    lokalna.PBN_WSTRZYMAJ_AUTOMATY = False
    wyjscie = _uruchom("--tak-to-jest-lokalna-kopia")
    assert "są WŁĄCZONE (DJANGO_BPP_PBN_WSTRZYMAJ_AUTOMATY=0)" in wyjscie


# --- odblokowanie automatów na lokalnej instancji ---------------------------


@pytest.fixture
def lokalna_wstrzymana(lokalna, db):
    """Lokalna instancja w stanie domyślnym: automaty wstrzymane, przełącznik
    dostępny. Po teście przełącznik wraca do „wstrzymane" — constance trzyma
    wartość także w cache (Redis), którego rollback transakcji nie cofa."""
    from constance import config

    lokalna.PBN_WSTRZYMAJ_AUTOMATY = True
    yield lokalna
    setattr(config, bezpiecznik.KLUCZ_ODBLOKOWANIA, False)


def test_domyslnie_wstrzymane_i_przelaczalne(lokalna_wstrzymana):
    stan = bezpiecznik.stan_automatow()
    assert (stan.wstrzymywanie_wlaczone, stan.wstrzymane, stan.przelaczalne) == (
        True,
        True,
        True,
    )


def test_odblokowanie_puszcza_automaty_i_da_sie_cofnac(
    lokalna_wstrzymana, redaktor, wydawnictwo_ciagle
):
    _wpis(redaktor, wydawnictwo_ciagle)

    bezpiecznik.ustaw_odblokowanie(True)
    assert bezpiecznik.automaty_wstrzymane() is False
    with patch(WYSLIJ) as wyslij:
        assert tasks.queue_watchdog() == 1
    wyslij.assert_called_once()

    bezpiecznik.ustaw_odblokowanie(False)
    assert bezpiecznik.automaty_wstrzymane() is True
    with patch(WYSLIJ) as wyslij:
        assert tasks.queue_watchdog() == 0
    wyslij.assert_not_called()


def test_odblokowanie_widzi_inny_proces(lokalna_wstrzymana):
    """Web i worker to osobne procesy: stan nie może siedzieć w pamięci.
    Sprawdzamy, że decyzja trafiła do bazy."""
    from constance.models import Constance

    bezpiecznik.ustaw_odblokowanie(True)

    zapisane = Constance.objects.get(key=bezpiecznik.KLUCZ_ODBLOKOWANIA).value
    assert '"__value__": true' in zapisane


def test_na_produkcji_przelacznik_nie_istnieje(settings, db):
    """Ustawienia produkcyjne: wstrzymywanie wyłączone, klucza constance nie
    ma — przełącznika nie da się ustawić i nic by nie zmienił."""
    settings.DEBUG = False
    settings.PBN_WSTRZYMAJ_AUTOMATY = False
    settings.CONSTANCE_CONFIG = {}

    assert bezpiecznik.automaty_wstrzymane() is False
    assert bezpiecznik.przelacznik_dostepny() is False
    with pytest.raises(bezpiecznik.PrzelacznikNiedostepny):
        bezpiecznik.ustaw_odblokowanie(False)
    with pytest.raises(bezpiecznik.PrzelacznikNiedostepny):
        bezpiecznik.ustaw_odblokowanie(True)


def test_ustawienia_produkcyjne_nie_maja_klucza_przelacznika():
    """Klucz constance dochodzi wyłącznie w settings/local.py."""
    from django_bpp.settings import base

    assert bezpiecznik.KLUCZ_ODBLOKOWANIA not in base.CONSTANCE_CONFIG


def test_odblokowanie_nie_dziala_na_instancji_nielokalnej(lokalna_wstrzymana):
    """Wartość „odblokowane" w bazie (np. z kopii bazy dewelopera) nie
    odblokowuje niczego, gdy instancja nie spełnia kryteriów lokalności."""
    bezpiecznik.ustaw_odblokowanie(True)
    assert bezpiecznik.automaty_wstrzymane() is False

    with patch("pbn_export_queue.bezpiecznik.host_bazy", return_value="dbserver"):
        assert bezpiecznik.automaty_wstrzymane() is True
        assert bezpiecznik.przelacznik_dostepny() is False
        with pytest.raises(bezpiecznik.PrzelacznikNiedostepny):
            bezpiecznik.ustaw_odblokowanie(True)

    lokalna_wstrzymana.DEBUG = False
    assert bezpiecznik.automaty_wstrzymane() is True


def test_komenda_ustawia_przelacznik(lokalna_wstrzymana):
    wyjscie = _uruchom("--tak-to-jest-lokalna-kopia", "--automaty", "wlacz")
    assert bezpiecznik.automaty_wstrzymane() is False
    assert "są WŁĄCZONE (odblokowane przełącznikiem)" in wyjscie

    # Bez --automaty przełącznik zostaje, jak był (logowanie do PBN nie cofa
    # świadomej decyzji dewelopera)…
    _uruchom("--tak-to-jest-lokalna-kopia")
    assert bezpiecznik.automaty_wstrzymane() is False

    # …a `wstrzymaj` go cofa.
    wyjscie = _uruchom("--tak-to-jest-lokalna-kopia", "--automaty", "wstrzymaj")
    assert bezpiecznik.automaty_wstrzymane() is True
    assert "WSTRZYMANE" in wyjscie


def test_komenda_odblokowujac_i_tak_zamyka_kolejke_z_kopii(
    lokalna_wstrzymana, redaktor, wydawnictwo_ciagle
):
    wpis = _wpis(redaktor, wydawnictwo_ciagle)

    _uruchom("--tak-to-jest-lokalna-kopia", "--automaty", "wlacz")

    wpis.refresh_from_db()
    assert wpis.wysylke_zakonczono is not None


@pytest.mark.parametrize(
    "opts,wstrzymane",
    [
        ({}, True),
        ({"pbn_automaty": "wstrzymaj"}, True),
        ({"pbn_automaty": "cokolwiek"}, True),
        ({"pbn_automaty": "wlacz"}, False),
        ({"pbn_automaty": "TAK"}, False),
    ],
)
def test_hook_run_site_ustawia_przelacznik_przy_kazdym_starcie(
    lokalna_wstrzymana, opts, wstrzymane
):
    from django_bpp import runsite_hooks

    # Odblokowanie z poprzedniej sesji nie przeżywa restartu bez flagi.
    bezpiecznik.ustaw_odblokowanie(True)

    runsite_hooks.zabezpiecz_lokalna_kopie({"opts": opts})

    assert bezpiecznik.automaty_wstrzymane() is wstrzymane


# --- przełącznik na stronie kolejki eksportu --------------------------------

ADRES_PRZELACZNIKA = "/pbn_export_queue/automaty/"
ADRES_KOLEJKI = "/pbn_export_queue/"


def test_strona_kolejki_pokazuje_stan_i_przelacza(lokalna_wstrzymana, admin_client):
    strona = admin_client.get(ADRES_KOLEJKI).content.decode()
    assert "automatyczna wysyłka do PBN: wstrzymana" in strona
    assert "Włącz automatyczną wysyłkę" in strona

    odpowiedz = admin_client.post(ADRES_PRZELACZNIKA, {"stan": "wlacz"})
    assert odpowiedz.status_code == 302
    assert bezpiecznik.automaty_wstrzymane() is False
    strona = admin_client.get(ADRES_KOLEJKI).content.decode()
    assert "automatyczna wysyłka do PBN: WŁĄCZONA" in strona
    assert "Wstrzymaj automatyczną wysyłkę" in strona

    admin_client.post(ADRES_PRZELACZNIKA, {"stan": "wstrzymaj"})
    assert bezpiecznik.automaty_wstrzymane() is True


def test_przelacznik_w_ui_wymaga_post_i_uprawnien(lokalna_wstrzymana, client):
    from model_bakery import baker

    assert client.post(ADRES_PRZELACZNIKA, {"stan": "wlacz"}).status_code == 302
    assert bezpiecznik.automaty_wstrzymane() is True  # niezalogowany

    client.force_login(baker.make(BppUser, is_active=True))
    client.post(ADRES_PRZELACZNIKA, {"stan": "wlacz"})
    assert bezpiecznik.automaty_wstrzymane() is True  # bez uprawnień

    assert client.get(ADRES_PRZELACZNIKA).status_code == 405


def test_na_produkcji_w_ui_nie_ma_przelacznika(settings, admin_client):
    settings.DEBUG = False
    settings.PBN_WSTRZYMAJ_AUTOMATY = False

    assert admin_client.post(ADRES_PRZELACZNIKA, {"stan": "wlacz"}).status_code == 404
    strona = admin_client.get(ADRES_KOLEJKI).content.decode()
    assert "pbn-automaty-stan" not in strona
    assert "automatyczna wysyłka do PBN" not in strona


def test_wstrzymywanie_wylaczone_zmienna_przelacznika_nie_ma(lokalna, admin_client):
    """Lokalna instancja z DJANGO_BPP_PBN_WSTRZYMAJ_AUTOMATY=0: automaty
    działają, a przełącznik (który nic by nie zmieniał) nie istnieje."""
    lokalna.PBN_WSTRZYMAJ_AUTOMATY = False

    assert bezpiecznik.przelacznik_dostepny() is False
    assert (
        admin_client.post(ADRES_PRZELACZNIKA, {"stan": "wstrzymaj"}).status_code == 404
    )
    assert "pbn-automaty-stan" not in admin_client.get(ADRES_KOLEJKI).content.decode()


def test_instancja_nielokalna_ze_wstrzymaniem_stan_bez_przycisku(
    lokalna_wstrzymana, admin_client
):
    """Np. dev-owy docker compose (baza pod nazwą serwisu): widać stan, ale
    przełączyć się nie da — ani z UI, ani żądaniem."""
    with patch("pbn_export_queue.bezpiecznik.host_bazy", return_value="db"):
        strona = admin_client.get(ADRES_KOLEJKI).content.decode()
        assert "automatyczna wysyłka do PBN: wstrzymana" in strona
        assert "Włącz automatyczną wysyłkę" not in strona
        odpowiedz = admin_client.post(ADRES_PRZELACZNIKA, {"stan": "wlacz"})
        assert odpowiedz.status_code == 404
    assert bezpiecznik.automaty_wstrzymane() is True


def test_ustawienia_testowe_nie_wstrzymuja_automatow():
    """Pilnuje settings/test.py: local.py włącza przełącznik domyślnie, a testy
    kolejki muszą widzieć automaty działające."""
    from django.conf import settings

    assert settings.PBN_WSTRZYMAJ_AUTOMATY is False
