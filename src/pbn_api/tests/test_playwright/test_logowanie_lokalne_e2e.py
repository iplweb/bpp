"""E2E ``pbn_zaloguj_lokalnie`` na ATRAPIE PBN.

Biorą udział dwa lokalne serwery HTTP:

- atrapa PBN (``http://127.0.0.1:<port A>``): strona logowania aplikacji,
  która od razu „loguje" i odsyła przeglądarkę na serwer klienta, wymiana
  ott→token i jeden endpoint odczytu. Zna KILKA aplikacji (po jednej na
  uczelnię) i pilnuje, żeby kod jednej nie przeszedł z tokenem drugiej,
- „serwer klienta" (``http://127.0.0.1:<port B>``) — prawdziwy, nasłuchujący
  serwer, który ZAPISUJE każde otrzymane żądanie. Powrót z PBN jest na niego
  kierowany tak jak na produkcję; test dowodzi, że nic do niego nie dociera.

Z prawdziwym PBN ani z żadnym serwerem klienta test się nie łączy.
"""

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from django.core.management import CommandError, call_command
from playwright.sync_api import Page

from bpp.models import Uczelnia
from bpp.models.profile import BppUser
from pbn_api.management.commands.pbn_zaloguj_lokalnie import Command
from pbn_export_queue.models import PBN_Export_Queue

APLIKACJA = "aplikacja-bpp"
TOKEN_APLIKACJI = "token-aplikacji-z-testu"
TOKEN_UZYTKOWNIKA = "token-uzytkownika-z-atrapy"
OTT = "0b7e-ott z+dziwnymi&znakami"

#: Druga uczelnia tej samej instalacji — własna aplikacja w PBN.
APLIKACJA_2 = "aplikacja-drugiej-uczelni"
TOKEN_APLIKACJI_2 = "token-aplikacji-drugiej"
DRUGI_TOKEN = "token-uzytkownika-z-aplikacji-drugiej"
OTT_2 = "ott-drugiej-uczelni"

#: aplikacja → (token aplikacji, kod OTT wydawany po zalogowaniu, token użytkownika)
APLIKACJE = {
    APLIKACJA: (TOKEN_APLIKACJI, OTT, TOKEN_UZYTKOWNIKA),
    APLIKACJA_2: (TOKEN_APLIKACJI_2, OTT_2, DRUGI_TOKEN),
}


class _Serwer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.zadania = []  # (metoda, path, naglowki, cialo)
        self.obsluga = lambda handler, cialo: handler.odpowiedz(404, "brak")
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_port}"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # cisza w wyjściu pytest

    def _obsluz(self):
        dlugosc = int(self.headers.get("Content-Length") or 0)
        cialo = self.rfile.read(dlugosc).decode() if dlugosc else ""
        self.server.zadania.append(
            (self.command, self.path, dict(self.headers.items()), cialo)
        )
        self.server.obsluga(self, cialo)

    do_GET = do_POST = _obsluz

    def odpowiedz(self, kod, tresc="", typ="text/html; charset=utf-8", **naglowki):
        dane = tresc.encode()
        self.send_response(kod)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(dane)))
        for nazwa, wartosc in naglowki.items():
            self.send_header(nazwa, wartosc)
        self.end_headers()
        self.wfile.write(dane)

    def json(self, dane, kod=200):
        self.odpowiedz(kod, json.dumps(dane), typ="application/json")


@pytest.fixture
def serwer_klienta():
    """„Produkcyjny" serwer klienta: przyjmuje wszystko i wszystko zapisuje."""
    serwer = _Serwer()
    serwer.obsluga = lambda h, cialo: h.odpowiedz(200, "<h1>serwer klienta</h1>")
    yield serwer
    serwer.shutdown()


@pytest.fixture
def atrapa_pbn(serwer_klienta):
    serwer = _Serwer()
    #: Co atrapa robi po „zalogowaniu" (dostaje kod OTT aplikacji);
    #: podmieniane w testach.
    serwer.powrot = lambda h, ott: h.odpowiedz(
        302,
        Location=f"{serwer_klienta.url}/pbn_api/callback?ott={_q(ott)}",
    )

    def obsluga(h, cialo):
        sciezka = urlsplit(h.path).path
        prefiks = "/auth/pbn/api/registration/user/token/"
        if sciezka.startswith(prefiks) and sciezka[len(prefiks) :] in APLIKACJE:
            return serwer.powrot(h, APLIKACJE[sciezka[len(prefiks) :]][1])
        aplikacja = APLIKACJE.get(h.headers.get("X-App-Id"))
        if aplikacja is None or h.headers.get("X-App-Token") != aplikacja[0]:
            return h.odpowiedz(400, "Mismatched X-APP-TOKEN: zly")
        token_aplikacji, ott, token_uzytkownika = aplikacja
        if sciezka == "/auth/pbn/api/user/token" and h.command == "POST":
            if json.loads(cialo).get("oneTimeToken") != ott:
                return h.json({"message": "invalid ott"})
            return h.json({"X-User-Token": token_uzytkownika})
        if sciezka == "/api/v1/institutionProfile/publications/page":
            if h.headers.get("X-User-Token") != token_uzytkownika:
                return h.json({"message": "Access Denied"}, kod=403)
            return h.json(
                {
                    "content": [],
                    "number": 0,
                    "totalElements": 7,
                    "totalPages": 1,
                    "pageable": {"pageNumber": 0},
                }
            )
        return h.odpowiedz(404, "nie ma")

    serwer.obsluga = obsluga
    yield serwer
    serwer.shutdown()


def _q(wartosc):
    from urllib.parse import quote

    return quote(wartosc, safe="")


def _ustaw_aplikacje(uczelnia, adres, aplikacja, token):
    # update(): Uczelnia.save() nie przyjmuje adresu API w sieci lokalnej
    # (ochrona przed SSRF), a atrapa PBN stoi na 127.0.0.1.
    Uczelnia.objects.filter(pk=uczelnia.pk).update(pbn_api_root=adres)
    uczelnia = Uczelnia.objects.get(pk=uczelnia.pk)
    uczelnia.pbn_app_name = aplikacja
    uczelnia.pbn_app_token = token
    uczelnia.pbn_integracja = True
    uczelnia.save()
    return uczelnia


@pytest.fixture
def lokalny_bpp(transactional_db, settings, uczelnia, admin_user, atrapa_pbn):
    settings.DEBUG = True
    uczelnia = _ustaw_aplikacje(uczelnia, atrapa_pbn.url, APLIKACJA, TOKEN_APLIKACJI)
    with patch("pbn_export_queue.bezpiecznik.host_bazy", return_value="localhost"):
        yield uczelnia


@pytest.fixture
def druga_uczelnia(lokalny_bpp, atrapa_pbn):
    """Instalacja z kilkoma uczelniami: druga ma WŁASNĄ aplikację PBN."""
    from django.contrib.sites.models import Site
    from model_bakery import baker

    druga = baker.make(
        Uczelnia,
        skrot="DRUGA",
        nazwa="Druga uczelnia",
        site=Site.objects.create(domain="druga.example.org", name="druga"),
    )
    return _ustaw_aplikacje(druga, atrapa_pbn.url, APLIKACJA_2, TOKEN_APLIKACJI_2)


def _zaloguj(page, **opcje):
    """Woła komendę tak jak ``bin/pbn-zaloguj-lokalnie.py``, tylko zamiast
    Chromium z trwałym profilem dostaje kontekst z pytest-playwright."""

    @contextmanager
    def kontekst_z_testu(profil, bez_okna):
        yield page.context

    out = StringIO()
    with patch.object(Command, "otworz_przegladarke", staticmethod(kontekst_z_testu)):
        call_command(
            "pbn_zaloguj_lokalnie",
            user="admin",
            limit_czasu=opcje.pop("limit_czasu", 60),
            stdout=out,
            **opcje,
        )
    return out.getvalue()


def _token_admina():
    return BppUser.objects.get(username="admin").pbn_token


def _wymiany_ott(atrapa_pbn):
    return [z for z in atrapa_pbn.zadania if z[1] == "/auth/pbn/api/user/token"]


@pytest.mark.parametrize("sciezka", ["/pbn_api/callback", "/pbn_api/kalbak/"])
def test_powrot_przekierowaniem_nie_wychodzi_do_serwera_klienta(
    lokalny_bpp, page: Page, atrapa_pbn, serwer_klienta, sciezka
):
    atrapa_pbn.powrot = lambda h, ott: h.odpowiedz(
        302, Location=f"{serwer_klienta.url}{sciezka}?ott={_q(OTT)}"
    )

    try:
        wyjscie = _zaloguj(page, limit_czasu=20)
    finally:
        # 1. Do serwera klienta nie dotarło ŻADNE żądanie. W ``finally``, bo
        #    gdy przechwycenie zawiedzie, komenda kończy się limitem czasu —
        #    a przyczyną ma być widoczny wyciek, nie timeout.
        assert serwer_klienta.zadania == [], "żądanie wyszło do serwera klienta"
    # 2. Przechwycony kod został wymieniony w (atrapie) PBN z poświadczeniami
    #    aplikacji uczelni.
    (wymiana,) = _wymiany_ott(atrapa_pbn)
    assert json.loads(wymiana[3]) == {"oneTimeToken": OTT}
    assert wymiana[2]["X-App-Id"] == APLIKACJA
    # 3. Token zapisany, zweryfikowany odczytem, i nigdzie niewypisany.
    assert _token_admina() == TOKEN_UZYTKOWNIKA
    assert "OK: token PBN użytkownika admin zapisany i działa" in wyjscie
    assert "w profilu instytucji: 7" in wyjscie
    assert TOKEN_UZYTKOWNIKA not in wyjscie
    assert TOKEN_APLIKACJI not in wyjscie
    assert f"GET {serwer_klienta.url}{sciezka}" in wyjscie
    assert "działa dla uczelni TE" in wyjscie
    # 4. Zamiast strony serwera klienta przeglądarka dostała naszą.
    assert "Kod z PBN przechwycony" in page.content()
    assert "serwer klienta" not in page.content()


def test_powrot_postem_tez_jest_przechwytywany(
    lokalny_bpp, page: Page, atrapa_pbn, serwer_klienta
):
    """Gdyby PBN wracał formularzem POST: kod jest w treści żądania."""
    atrapa_pbn.powrot = lambda h, ott: h.odpowiedz(
        200,
        f'<form id="f" method="post" action="{serwer_klienta.url}/pbn_api/callback">'
        f'<input name="ott" value="{OTT}"></form>'
        '<script>document.getElementById("f").submit()</script>',
    )

    wyjscie = _zaloguj(page)

    assert serwer_klienta.zadania == []
    assert _token_admina() == TOKEN_UZYTKOWNIKA
    assert f"POST {serwer_klienta.url}/pbn_api/callback" in wyjscie


def test_powrot_na_nieznana_sciezke_kod_wymieniany_bezposrednio(
    lokalny_bpp, page: Page, atrapa_pbn, serwer_klienta
):
    """PBN wraca z ``ott`` na adres, który nie jest callbackiem BPP: żądanie
    nadal nie wychodzi, a kod jest wymieniany tą samą drogą co ``--ott``."""
    atrapa_pbn.powrot = lambda h, ott: h.odpowiedz(
        302, Location=f"{serwer_klienta.url}/zupelnie/inny/adres?ott={_q(OTT)}"
    )

    wyjscie = _zaloguj(page)

    assert serwer_klienta.zadania == []
    assert _token_admina() == TOKEN_UZYTKOWNIKA
    assert f"GET {serwer_klienta.url}/zupelnie/inny/adres" in wyjscie
    assert "Kod z PBN przechwycony" in page.content()


def test_powrot_bez_kodu_czytelny_blad_i_nic_nie_wychodzi(
    lokalny_bpp, page: Page, atrapa_pbn, serwer_klienta
):
    atrapa_pbn.powrot = lambda h, ott: h.odpowiedz(
        200,
        f'<form id="f" method="post" action="{serwer_klienta.url}/pbn_api/callback">'
        '<input name="cos_innego" value="x"></form>'
        '<script>document.getElementById("f").submit()</script>',
    )

    with pytest.raises(CommandError, match="BEZ kodu OTT"):
        _zaloguj(page)

    assert serwer_klienta.zadania == []
    assert _token_admina() == ""


def test_limit_czasu_gdy_nikt_sie_nie_zaloguje(
    lokalny_bpp, page: Page, atrapa_pbn, serwer_klienta
):
    atrapa_pbn.powrot = lambda h, ott: h.odpowiedz(200, "<h1>Logowanie do PBN</h1>")

    with pytest.raises(CommandError, match="limit czasu"):
        _zaloguj(page, limit_czasu=2)

    assert _token_admina() == ""


def test_dzialajacy_token_pomija_logowanie(
    lokalny_bpp, page: Page, atrapa_pbn, admin_user
):
    admin_user.pbn_token = TOKEN_UZYTKOWNIKA
    admin_user.save()

    wyjscie = _zaloguj(page)

    assert "OK: token PBN użytkownika admin działa" in wyjscie
    assert _wymiany_ott(atrapa_pbn) == []
    assert not [z for z in atrapa_pbn.zadania if "registration" in z[1]]


def test_logowanie_zamyka_kolejke_i_niczego_nie_wysyla(
    lokalny_bpp,
    page: Page,
    atrapa_pbn,
    serwer_klienta,
    admin_user,
    wydawnictwo_ciagle,
):
    """Kopia bazy produkcyjnej: w kolejce czeka wpis „wyślij po zalogowaniu".
    Po zalogowaniu atrapa PBN nie może dostać żadnego zapisu."""
    from model_bakery import baker

    wpis = baker.make(
        PBN_Export_Queue,
        zamowil=admin_user,
        rekord_do_wysylki=wydawnictwo_ciagle,
        retry_after_user_authorised=True,
    )

    wyjscie = _zaloguj(page)

    assert _token_admina() == TOKEN_UZYTKOWNIKA
    wpis.refresh_from_db()
    assert wpis.wysylke_zakonczono is not None
    assert wpis.ilosc_prob == 0
    assert "zamknięto 1 wpis(ów) wysyłki" in wyjscie
    # Jedyne żądania do PBN: strona logowania, wymiana ott, jeden odczyt.
    assert sorted({(z[0], urlsplit(z[1]).path) for z in atrapa_pbn.zadania}) == [
        ("GET", "/api/v1/institutionProfile/publications/page"),
        ("GET", f"/auth/pbn/api/registration/user/token/{APLIKACJA}"),
        ("POST", "/auth/pbn/api/user/token"),
    ]


def test_tryb_awaryjny_ott_bez_przegladarki(lokalny_bpp, atrapa_pbn):
    out = StringIO()

    with patch.object(Command, "otworz_przegladarke") as przegladarka:
        call_command("pbn_zaloguj_lokalnie", user="admin", ott=OTT, stdout=out)

    przegladarka.assert_not_called()
    assert _token_admina() == TOKEN_UZYTKOWNIKA
    assert "zapisany i działa" in out.getvalue()
    assert TOKEN_UZYTKOWNIKA not in out.getvalue()


def test_tylko_sprawdz_wykrywa_token_odrzucany_przez_pbn(
    lokalny_bpp, atrapa_pbn, admin_user
):
    """„Zapisany" to nie „działa": końcowe sprawdzenie naprawdę pyta PBN."""
    admin_user.pbn_token = "token-ktorego-pbn-nie-zna"
    admin_user.save()

    with pytest.raises(CommandError, match="PBN.*go ODRZUCA") as e:
        call_command(
            "pbn_zaloguj_lokalnie", user="admin", tylko_sprawdz=True, stdout=StringIO()
        )

    assert "token-ktorego-pbn-nie-zna" not in str(e.value)
    assert [z[0] for z in atrapa_pbn.zadania] == ["GET"]


def test_kilka_uczelni_logowanie_przez_aplikacje_wskazanej(
    lokalny_bpp, druga_uczelnia, page: Page, atrapa_pbn, serwer_klienta
):
    """Instalacja z kilkoma uczelniami: ``--uczelnia DRUGA`` prowadzi przez
    aplikację PBN DRUGIEJ uczelni (nie pierwszej z brzegu) i tę samą potem
    sprawdza."""
    wyjscie = _zaloguj(page, uczelnia="DRUGA")

    assert serwer_klienta.zadania == []
    logowania = [
        urlsplit(z[1]).path for z in atrapa_pbn.zadania if "registration" in z[1]
    ]
    assert logowania == [f"/auth/pbn/api/registration/user/token/{APLIKACJA_2}"]
    (wymiana,) = _wymiany_ott(atrapa_pbn)
    assert wymiana[2]["X-App-Id"] == APLIKACJA_2
    assert wymiana[2]["X-App-Token"] == TOKEN_APLIKACJI_2
    assert json.loads(wymiana[3]) == {"oneTimeToken": OTT_2}
    assert _token_admina() == DRUGI_TOKEN
    assert "działa dla uczelni DRUGA" in wyjscie
    assert f"aplikację PBN „{APLIKACJA_2}” uczelni DRUGA" in wyjscie
    # Żadne żądanie nie poszło z poświadczeniami pierwszej uczelni.
    assert not [z for z in atrapa_pbn.zadania if z[2].get("X-App-Id") == APLIKACJA]


def test_kilka_uczelni_bez_wskazania_lista_do_wyboru(
    lokalny_bpp, druga_uczelnia, atrapa_pbn
):
    with patch.object(Command, "otworz_przegladarke") as przegladarka:
        with pytest.raises(CommandError, match="kilka uczelni.*TE.*DRUGA"):
            call_command("pbn_zaloguj_lokalnie", user="admin", stdout=StringIO())

    przegladarka.assert_not_called()
    assert atrapa_pbn.zadania == []


def test_kilka_uczelni_token_jednej_nie_dziala_dla_drugiej(
    lokalny_bpp, druga_uczelnia, atrapa_pbn, admin_user
):
    """Końcowe sprawdzenie pyta PBN jako WSKAZANA uczelnia."""
    admin_user.pbn_token = DRUGI_TOKEN
    admin_user.save()

    out = StringIO()
    call_command(
        "pbn_zaloguj_lokalnie",
        user="admin",
        uczelnia="DRUGA",
        tylko_sprawdz=True,
        stdout=out,
    )
    assert "działa dla uczelni DRUGA" in out.getvalue()

    with pytest.raises(CommandError, match="ODRZUCA dla uczelni TE"):
        call_command(
            "pbn_zaloguj_lokalnie",
            user="admin",
            uczelnia="TE",
            tylko_sprawdz=True,
            stdout=StringIO(),
        )


def test_odmowa_na_nielokalnej_instancji(lokalny_bpp, settings, atrapa_pbn):
    settings.DEBUG = False

    with pytest.raises(CommandError, match="ODMOWA"):
        call_command("pbn_zaloguj_lokalnie", user="admin", ott=OTT, stdout=StringIO())

    assert atrapa_pbn.zadania == []
    assert _token_admina() == ""


def test_token_aplikacji_zaszyfrowany_innym_kluczem(lokalny_bpp, settings, atrapa_pbn):
    """Kopia bazy z serwera: token aplikacji nieczytelny → instrukcja, a nie
    „Brak tokena aplikacji" z głębi klienta PBN."""
    from cryptography.fernet import Fernet

    settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
    settings.DSPACE_CREDENTIALS_KEY = ""

    with pytest.raises(CommandError) as e:
        call_command("pbn_zaloguj_lokalnie", user="admin", ott=OTT, stdout=StringIO())

    assert "zaszyfrowany INNYM kluczem" in str(e.value)
    assert "--konfiguracja-z HOST" in str(e.value)
    assert atrapa_pbn.zadania == []


def test_ott_z_zadania():
    from pbn_api.logowanie_lokalne import ott_z_zadania

    u = "https://k.example.invalid/pbn_api/callback"
    assert ott_z_zadania({"url": u + "?ott=a%20b"}) == "a b"
    assert ott_z_zadania({"url": u, "postData": "x=1&ott=c%2Bd"}) == "c+d"
    assert ott_z_zadania({"url": u, "postData": '{"ott": "e"}'}) == "e"
    assert ott_z_zadania({"url": u, "postData": '{"oneTimeToken": "f"}'}) == "f"
    assert ott_z_zadania({"url": u, "postData": "nic=tu"}) is None
    assert ott_z_zadania({"url": u}) is None
    assert parse_qs("ott=") == {}
