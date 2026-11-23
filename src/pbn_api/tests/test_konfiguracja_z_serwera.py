"""Przeniesienie konfiguracji aplikacji PBN serwer → lokalna kopia, przy
RÓŻNYCH kluczach szyfrowania po obu stronach."""

import shlex
import subprocess
from io import StringIO
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet, InvalidToken
from django.core.management import CommandError, call_command
from django.db import connection
from model_bakery import baker

from bpp.fields import NieodszyfrowanaWartosc
from bpp.models import Uczelnia
from bpp.models.profile import BppUser
from pbn_api import konfiguracja_z_serwera as kzs

KLUCZ_SERWERA = Fernet.generate_key().decode()
KLUCZ_LOKALNY = Fernet.generate_key().decode()

TOKEN_APLIKACJI = "tajny-token-aplikacji-PBN"
TOKEN_UZYTKOWNIKA = "tajny-token-uzytkownika-PBN"
DELAY = "pbn_export_queue.tasks.kolejka_ponow_wysylke_prac_po_zalogowaniu.delay"


def _ustaw_klucz(settings, klucz):
    settings.FIELD_ENCRYPTION_KEY = klucz
    settings.DSPACE_CREDENTIALS_KEY = ""


def _surowa(tabela, kolumna, pk):
    with connection.cursor() as cur:
        cur.execute(f"SELECT {kolumna} FROM {tabela} WHERE id = %s", [pk])  # noqa: S608
        return cur.fetchone()[0]


@pytest.fixture
def serwer(settings, uczelnia):
    """Stan bazy „jak na serwerze": sekrety zaszyfrowane kluczem serwera."""
    _ustaw_klucz(settings, KLUCZ_SERWERA)
    uczelnia.pbn_api_root = "https://pbn.example.org"
    uczelnia.pbn_app_name = "aplikacja-bpp"
    uczelnia.pbn_app_token = TOKEN_APLIKACJI
    uczelnia.pbn_integracja = True
    uczelnia.save()
    user = baker.make(
        BppUser, username="redaktor", is_active=True, pbn_token=TOKEN_UZYTKOWNIKA
    )
    return uczelnia, user


def _wyjscie_zdalnego_skryptu(capsys, login="redaktor", skrot=None):
    """Wykonuje DOKŁADNIE ten kod, który poleci na serwer, tą samą drogą
    (``manage.py shell -c``), i zwraca jego stdout."""
    capsys.readouterr()
    call_command("shell", command=kzs.zdalny_skrypt(login, skrot))
    return capsys.readouterr().out


def _odtworz_kopie_lokalnie(settings):
    """Dump serwera odtworzony lokalnie = te same szyfrogramy, inny klucz."""
    _ustaw_klucz(settings, KLUCZ_LOKALNY)


@pytest.mark.django_db
def test_pole_szyfrowane_przy_zlym_kluczu_czyta_sie_jako_puste(serwer, settings):
    """Punkt wyjścia całego narzędzia: zły klucz to nie wyjątek, tylko pusta
    wartość pamiętająca szyfrogram."""
    uczelnia, user = serwer
    _odtworz_kopie_lokalnie(settings)

    uczelnia = Uczelnia.objects.get(pk=uczelnia.pk)
    user = BppUser.objects.get(pk=user.pk)

    for wartosc in (uczelnia.pbn_app_token, user.pbn_token):
        assert wartosc == ""
        assert not wartosc
        assert isinstance(wartosc, NieodszyfrowanaWartosc)
        assert wartosc.szyfrogram.startswith("gAAAAA")


@pytest.mark.django_db
def test_przeniesienie_miedzy_roznymi_kluczami(
    serwer, settings, capsys, django_capture_on_commit_callbacks
):
    uczelnia, user = serwer
    wyjscie = _wyjscie_zdalnego_skryptu(capsys)
    _odtworz_kopie_lokalnie(settings)
    assert not Uczelnia.objects.get(pk=uczelnia.pk).pbn_app_token

    # execute=True: ponowienie kolejki jest zlecane w on_commit — bez
    # wykonania tych callbacków asercja „nie ruszono kolejki" byłaby pusta.
    with patch(DELAY) as delay, django_capture_on_commit_callbacks(execute=True):
        raport = kzs.zastosuj(kzs.rozbierz_odpowiedz(wyjscie))

    uczelnia = Uczelnia.objects.get(pk=uczelnia.pk)
    user = BppUser.objects.get(pk=user.pk)
    assert uczelnia.pbn_app_token == TOKEN_APLIKACJI
    assert uczelnia.pbn_app_name == "aplikacja-bpp"
    assert uczelnia.pbn_api_root == "https://pbn.example.org"
    assert user.pbn_token == TOKEN_UZYTKOWNIKA

    # W bazie leży szyfrogram LOKALNEGO klucza, nie serwera i nie jawny tekst.
    for surowa, jawna in (
        (_surowa("bpp_uczelnia", "pbn_app_token", uczelnia.pk), TOKEN_APLIKACJI),
        (_surowa("bpp_bppuser", "pbn_token", user.pk), TOKEN_UZYTKOWNIKA),
    ):
        assert surowa != jawna
        assert Fernet(KLUCZ_LOKALNY).decrypt(surowa.encode()).decode() == jawna
        with pytest.raises(InvalidToken):
            Fernet(KLUCZ_SERWERA).decrypt(surowa.encode())

    # Przeniesienie tokenu to nie „zalogowanie" — kolejka eksportu nie rusza.
    delay.assert_not_called()
    # Raport nie zawiera sekretów.
    tekst = "\n".join(raport)
    assert TOKEN_APLIKACJI not in tekst
    assert TOKEN_UZYTKOWNIKA not in tekst
    assert "aplikacja-bpp" in tekst


@pytest.mark.django_db
def test_wyjscie_z_szumem_powloki_django(serwer, settings, capsys):
    """Nowsze Django dopisuje do stdout `shell` własne komunikaty — bierzemy
    tylko wiersz ze znacznikiem."""
    wyjscie = _wyjscie_zdalnego_skryptu(capsys)
    zaszumione = "12 objects imported automatically.\n\n" + wyjscie + "\nbye\n"

    dane = kzs.rozbierz_odpowiedz(zaszumione)

    assert dane["pbn_app_token"] == TOKEN_APLIKACJI
    assert dane["uzytkownik"]["pbn_token"] == TOKEN_UZYTKOWNIKA


@pytest.mark.django_db
def test_serwer_sam_nie_umie_odszyfrowac(serwer, settings, capsys):
    """Serwer ze zgubionym kluczem zwraca puste wartości → czytelny błąd,
    lokalna konfiguracja nietknięta."""
    _ustaw_klucz(settings, Fernet.generate_key().decode())
    wyjscie = _wyjscie_zdalnego_skryptu(capsys)
    _odtworz_kopie_lokalnie(settings)

    with pytest.raises(kzs.BladPrzenoszenia, match="nie zwrócił nazwy lub tokenu"):
        kzs.zastosuj(kzs.rozbierz_odpowiedz(wyjscie))


@pytest.mark.django_db
def test_brak_uzytkownika_na_serwerze_nie_blokuje_konfiguracji(
    serwer, settings, capsys
):
    uczelnia, _ = serwer
    wyjscie = _wyjscie_zdalnego_skryptu(capsys, login="nie-ma-takiego")
    _odtworz_kopie_lokalnie(settings)

    raport = "\n".join(kzs.zastosuj(kzs.rozbierz_odpowiedz(wyjscie)))

    assert Uczelnia.objects.get(pk=uczelnia.pk).pbn_app_token == TOKEN_APLIKACJI
    assert "UWAGA: na serwerze nie ma użytkownika 'nie-ma-takiego'" in raport


@pytest.mark.django_db
def test_kilka_uczelni_na_serwerze_wymaga_wskazania(serwer, capsys):
    baker.make(Uczelnia, skrot="DRUGA")

    dane = kzs.rozbierz_odpowiedz(_wyjscie_zdalnego_skryptu(capsys))
    assert "kilka uczelni" in dane["blad"]
    with pytest.raises(kzs.BladPrzenoszenia, match="kilka uczelni"):
        kzs.zastosuj(dane)

    dane = kzs.rozbierz_odpowiedz(_wyjscie_zdalnego_skryptu(capsys, skrot="TE"))
    assert dane["blad"] is None
    assert dane["pbn_app_token"] == TOKEN_APLIKACJI


def test_brak_znacznika_w_odpowiedzi():
    with pytest.raises(kzs.BladPrzenoszenia, match="nie ma konfiguracji PBN"):
        kzs.rozbierz_odpowiedz("Error: No such service: appserver\n")


def test_uszkodzony_json_nie_cytuje_tresci():
    with pytest.raises(kzs.BladPrzenoszenia) as e:
        kzs.rozbierz_odpowiedz(kzs.ZNACZNIK + '{"pbn_app_token": "sekret-urw')
    assert "sekret-urw" not in str(e.value)


def test_zdalne_polecenie_przechodzi_przez_powloke_bez_zmian():
    """Polecenie jedzie przez ssh → powłokę serwera; po rozbiorze przez
    powłokę ostatni argument musi być bajt w bajt naszym skryptem."""
    polecenie = kzs.zdalne_polecenie("o'brien", "U W", "~/moj deploy", "appserver")

    argumenty = shlex.split(polecenie)

    assert argumenty[:3] == ["cd", "~/moj deploy", "&&"]
    assert argumenty[3:11] == [
        "docker", "compose", "exec", "-T", "appserver",
        "python", "src/manage.py", "shell",
    ]  # fmt: skip
    assert argumenty[11] == "-c"
    assert argumenty[12] == kzs.zdalny_skrypt("o'brien", "U W")
    assert polecenie.startswith("cd ~/'moj deploy' && ")
    compile(argumenty[12], "<zdalny skrypt>", "exec")


@pytest.mark.parametrize(
    "zrodlo,oczekiwane",
    [
        ("admin@serwer", ("admin", "serwer")),
        ("jan@uczelnia.example@serwer", ("jan@uczelnia.example", "serwer")),
        ("serwer", (None, "serwer")),
    ],
)
def test_rozbierz_zrodlo(zrodlo, oczekiwane):
    assert kzs.rozbierz_zrodlo(zrodlo) == oczekiwane


@pytest.mark.parametrize("zrodlo", ["@serwer", "admin@", "", "admin@-oProxyCommand=x"])
def test_rozbierz_zrodlo_odrzuca(zrodlo):
    with pytest.raises(kzs.BladPrzenoszenia):
        kzs.rozbierz_zrodlo(zrodlo)


def _falszywe_ssh(stdout, returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


@pytest.mark.django_db
def test_komenda_przez_ssh_najpierw_bezpiecznik(serwer, settings, capsys):
    uczelnia, user = serwer
    wyjscie = _wyjscie_zdalnego_skryptu(capsys)
    _odtworz_kopie_lokalnie(settings)
    settings.DEBUG = True
    out = StringIO()

    with (
        patch("pbn_export_queue.bezpiecznik.host_bazy", return_value="localhost"),
        patch.object(kzs.subprocess, "run", return_value=_falszywe_ssh(wyjscie)) as ssh,
    ):
        call_command("pbn_konfiguracja_z_serwera", "redaktor@serwer-x", stdout=out)

    argv = ssh.call_args.args[0]
    assert argv[:2] == ["ssh", "serwer-x"]
    assert TOKEN_APLIKACJI not in argv[2]
    assert Uczelnia.objects.get(pk=uczelnia.pk).pbn_app_token == TOKEN_APLIKACJI
    assert BppUser.objects.get(pk=user.pk).pbn_token == TOKEN_UZYTKOWNIKA
    raport = out.getvalue()
    assert "Kolejka eksportu do PBN: zamknięto" in raport
    assert TOKEN_APLIKACJI not in raport
    assert TOKEN_UZYTKOWNIKA not in raport


@pytest.mark.django_db
def test_komenda_na_nielokalnej_instancji_niczego_nie_pobiera(serwer, settings):
    settings.DEBUG = False

    with patch.object(kzs.subprocess, "run") as ssh:
        with pytest.raises(CommandError, match="ODMOWA"):
            call_command("pbn_konfiguracja_z_serwera", "redaktor@serwer-x")

    ssh.assert_not_called()


@pytest.mark.django_db
def test_komenda_blad_ssh_bez_stdout_w_komunikacie(serwer, settings):
    settings.DEBUG = True
    odpowiedz = _falszywe_ssh(
        kzs.ZNACZNIK + '{"pbn_app_token": "wyciek"}', 255, "Permission denied"
    )

    with (
        patch("pbn_export_queue.bezpiecznik.host_bazy", return_value="localhost"),
        patch.object(kzs.subprocess, "run", return_value=odpowiedz),
    ):
        with pytest.raises(CommandError) as e:
            call_command(
                "pbn_konfiguracja_z_serwera", "redaktor@serwer-x", stdout=StringIO()
            )

    assert "Permission denied" in str(e.value)
    assert "wyciek" not in str(e.value)


@pytest.mark.django_db
def test_hook_run_site_przekazuje_zrodlo_i_nie_wywraca_stacku(serwer, settings):
    from django_bpp import runsite_hooks

    settings.DEBUG = True
    with (
        patch("pbn_export_queue.bezpiecznik.host_bazy", return_value="localhost"),
        patch.object(
            kzs.subprocess, "run", return_value=_falszywe_ssh("", 255, "no route")
        ) as ssh,
    ):
        runsite_hooks.fetch_pbn_token({"opts": {}})
        ssh.assert_not_called()

        runsite_hooks.fetch_pbn_token(
            {
                "opts": {
                    "pbn_ssh_source": "redaktor@serwer-x",
                    "pbn_remote_deploy_path": "~/inny-deploy",
                    "pbn_remote_compose_service": "appserver",
                }
            }
        )

    argv = ssh.call_args.args[0]
    assert argv[:2] == ["ssh", "serwer-x"]
    assert argv[2].startswith("cd ~/inny-deploy && docker compose exec -T appserver ")
