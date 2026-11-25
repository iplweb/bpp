"""Przeniesienie konfiguracji aplikacji PBN z serwera na lokalną instancję.

``Uczelnia.pbn_app_token`` i ``BppUser.pbn_token`` to pola szyfrowane kluczem
``DJANGO_BPP_FIELD_ENCRYPTION_KEY``. Po odtworzeniu dumpu produkcyjnego na
maszynie dewelopera klucz jest inny, więc oba pola czytają się jako puste
(``bpp.fields.NieodszyfrowanaWartosc``) i autoryzacja w PBN kończy się
„Brak tokena aplikacji". Zamiast kopiować klucz serwera, prosimy serwer
o wartości JAWNE (odszyfrowuje je tamtejszy ORM), a lokalny zapis szyfruje
je kluczem lokalnym.

Po stronie serwera uruchamiamy ``manage.py shell -c`` z kodem z
:data:`ZDALNY_SKRYPT` — nie wymaga to żadnej nowej komendy w obrazie, więc
działa z serwerami na dowolnej wydanej wersji BPP.

Sekrety idą wyłącznie potokiem SSH → pamięć tego procesu → baza. Nie
trafiają na stdout, do logów ani na dysk.
"""

import json
import shlex
import subprocess
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime

#: Wiersz stdout zaczynający się od tego znacznika niesie JSON. Wszystko inne
#: (np. „N objects imported automatically" z nowszych wersji Django) pomijamy.
ZNACZNIK = "BPP_PBN_KONFIGURACJA_JSON:"

#: Kod wykonywany na serwerze przez ``manage.py shell -c``. Płaski (bez
#: funkcji i wyrażeń listowych), żeby nie zależał od tego, jak dana wersja
#: Django woła ``exec``. Parametry przychodzą przez ``%r`` — skrypt nie
#: czyta stdin ani zmiennych środowiskowych.
ZDALNY_SKRYPT = """
import json
from django.contrib.auth import get_user_model
from bpp.models import Uczelnia
_login = %(login)r
_wynik = {"wersja": 2, "blad": None, "uczelnie": [], "uzytkownik": None}
for _u in Uczelnia.objects.order_by("pk"):
    _wynik["uczelnie"].append(
        {
            "skrot": str(_u.skrot),
            "pbn_api_root": str(_u.pbn_api_root or ""),
            "pbn_app_name": str(_u.pbn_app_name or ""),
            "pbn_app_token": str(_u.pbn_app_token or ""),
        }
    )
if not _wynik["uczelnie"]:
    _wynik["blad"] = "na serwerze nie ma zadnej uczelni"
if _login:
    _user = get_user_model().objects.filter(username=_login).first()
    if _user is None:
        _wynik["uzytkownik"] = {"username": _login, "istnieje": False}
    else:
        _kiedy = _user.pbn_token_updated
        _wynik["uzytkownik"] = {
            "username": _login,
            "istnieje": True,
            "pbn_token": str(_user.pbn_token or ""),
            "pbn_token_updated": _kiedy.isoformat() if _kiedy else None,
        }
print(%(znacznik)r + json.dumps(_wynik))
"""


class BladPrzenoszenia(Exception):
    """Czytelny dla człowieka błąd przenoszenia konfiguracji PBN."""


def zdalny_skrypt(login=None) -> str:
    return ZDALNY_SKRYPT % {"login": login or "", "znacznik": ZNACZNIK}


def rozbierz_zrodlo(zrodlo: str) -> tuple[str | None, str]:
    """``LOGIN@HOST`` → ``(login, host)``; samo ``HOST`` → ``(None, host)``.

    LOGIN to nazwa użytkownika BPP (nie konto SSH) — taka sama konwencja
    jak dotychczasowe ``--get-pbn-token-from``. HOST to alias z
    ``~/.ssh/config``.
    """
    login, malpa, host = zrodlo.rpartition("@")
    if not host or (malpa and not login):
        raise BladPrzenoszenia(
            f"Nieprawidłowe źródło {zrodlo!r} — oczekiwano LOGIN@HOST albo HOST."
        )
    if host.startswith("-"):
        # ``ssh -oProxyCommand=…`` — host nie może być opcją ssh.
        raise BladPrzenoszenia(f"Nieprawidłowa nazwa hosta SSH: {host!r}.")
    return (login or None), host


def _zacytuj_sciezke_zdalna(sciezka: str) -> str:
    # shlex.quote("~/foo") → "'~/foo'", a powłoka nie rozwija ``~`` w
    # cudzysłowach. Wiodące ``~/`` zostaje poza cytowaniem.
    if sciezka == "~" or sciezka.startswith("~/"):
        glowa, _, ogon = sciezka.partition("/")
        if not ogon:
            return glowa
        return f"{glowa}/{shlex.quote(ogon)}"
    return shlex.quote(sciezka)


def zdalne_polecenie(
    login=None,
    remote_deploy_path="~/bpp-deploy",
    remote_compose_service="appserver",
) -> str:
    """Polecenie powłoki dla serwera. Nie zawiera żadnych sekretów."""
    return (
        f"cd {_zacytuj_sciezke_zdalna(remote_deploy_path)} && "
        f"docker compose exec -T {shlex.quote(remote_compose_service)} "
        f"python src/manage.py shell -c {shlex.quote(zdalny_skrypt(login))}"
    )


def rozbierz_odpowiedz(stdout: str) -> dict:
    """Wyciąga JSON z wyjścia zdalnego skryptu."""
    for linia in reversed(stdout.splitlines()):
        if linia.startswith(ZNACZNIK):
            try:
                dane = json.loads(linia[len(ZNACZNIK) :])
            except json.JSONDecodeError as e:
                # Treści nie cytujemy — może zawierać sekret.
                raise BladPrzenoszenia(
                    "Serwer zwrócił uszkodzony JSON konfiguracji PBN."
                ) from e
            if not isinstance(dane, dict):
                raise BladPrzenoszenia("Serwer zwrócił JSON w nieznanym formacie.")
            return dane
    raise BladPrzenoszenia(
        "W odpowiedzi serwera nie ma konfiguracji PBN (brak wiersza "
        f"{ZNACZNIK}…). Sprawdź ścieżkę bpp-deploy i nazwę serwisu."
    )


def pobierz_z_serwera(
    ssh_host,
    login=None,
    remote_deploy_path="~/bpp-deploy",
    remote_compose_service="appserver",
    timeout=120,
) -> dict:
    polecenie = zdalne_polecenie(login, remote_deploy_path, remote_compose_service)
    try:
        wynik = subprocess.run(
            ["ssh", ssh_host, polecenie],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise BladPrzenoszenia("Nie znaleziono polecenia `ssh`.") from e
    except subprocess.TimeoutExpired as e:
        raise BladPrzenoszenia(
            f"Brak odpowiedzi z {ssh_host} w ciągu {timeout} s."
        ) from e
    if wynik.returncode != 0:
        # stderr to komunikaty ssh/docker/Django, nie dane — stdout (z
        # sekretami) nie jest cytowany nigdy.
        raise BladPrzenoszenia(
            f"Polecenie na {ssh_host} zakończyło się kodem {wynik.returncode}: "
            f"{wynik.stderr.strip()[-2000:] or '(puste stderr)'}"
        )
    return rozbierz_odpowiedz(wynik.stdout)


def _dopasuj_uczelnie(zdalne, skrot=None):
    """Pary ``(lokalna uczelnia, konfiguracja z serwera)``.

    Kopia bazy ma te same skróty co serwer, więc parujemy po skrócie —
    także w instalacji z kilkoma uczelniami (każda ma własną aplikację PBN).
    Jedna uczelnia po obu stronach paruje się niezależnie od skrótu.
    ``skrot`` zawęża do jednej uczelni.
    """
    from bpp.models import Uczelnia

    lokalne = list(Uczelnia.objects.order_by("pk"))
    if not lokalne:
        raise BladPrzenoszenia("W lokalnej bazie nie ma żadnej uczelni.")
    if skrot:
        lokalne = [u for u in lokalne if u.skrot == skrot]
        zdalne = [z for z in zdalne if z.get("skrot") == skrot]
        if not lokalne or not zdalne:
            raise BladPrzenoszenia(
                f"Uczelni o skrócie {skrot!r} nie ma "
                f"{'w lokalnej bazie' if not lokalne else 'na serwerze'}."
            )
    if len(lokalne) == 1 and len(zdalne) == 1:
        return [(lokalne[0], zdalne[0])]
    po_skrocie = {z.get("skrot"): z for z in zdalne}
    return [(u, po_skrocie[u.skrot]) for u in lokalne if u.skrot in po_skrocie]


def _zastosuj_uczelnie(uczelnia, zdalna, raport) -> bool:
    root = (zdalna.get("pbn_api_root") or "").rstrip("/")
    nazwa = zdalna.get("pbn_app_name") or ""
    token = zdalna.get("pbn_app_token") or ""
    if not nazwa or not token or urlsplit(root).scheme not in ("http", "https"):
        raport.append(
            f"UWAGA: uczelnia {uczelnia.skrot} — serwer nie zwrócił kompletnej "
            "konfiguracji aplikacji PBN (brak integracji albo serwer sam nie "
            "potrafi odszyfrować tokenu: `manage.py check`, bpp.W103). Pominięto."
        )
        return False

    uczelnia.pbn_api_root = root
    uczelnia.pbn_app_name = nazwa
    uczelnia.pbn_app_token = token
    pola = ["pbn_api_root", "pbn_app_name", "pbn_app_token"]
    wlaczono_integracje = not uczelnia.pbn_integracja
    if wlaczono_integracje:
        uczelnia.pbn_integracja = True
        pola.append("pbn_integracja")
    try:
        uczelnia.save(update_fields=pola)
    except ValidationError as e:
        # Uczelnia.save() woła clean() — m.in. odrzuca adres API wskazujący
        # na sieć prywatną. Komunikaty walidacji nie zawierają sekretów.
        raise BladPrzenoszenia(
            f"Lokalna uczelnia {uczelnia.skrot} nie przechodzi walidacji przy "
            f"zapisie: {'; '.join(e.messages)}"
        ) from e
    raport.append(
        f"Konfiguracja aplikacji PBN uczelni {uczelnia.skrot}: zapisana "
        f"(adres API {root}, aplikacja {nazwa}, token aplikacji zaszyfrowany "
        "lokalnym kluczem)."
    )
    if wlaczono_integracje:
        raport.append(
            f"Uczelnia {uczelnia.skrot}: włączono „Czy używać integracji "
            "z PBN?” (pbn_integracja)."
        )
    if not uczelnia.pbn_aktualizuj_na_biezaco:
        raport.append(
            f"Uczelnia {uczelnia.skrot}: przyciski „Zapisz i wyślij do PBN” są "
            "wyłączone (pbn_aktualizuj_na_biezaco) — włącz w adminie uczelni, "
            "jeśli chcesz testować ręczną wysyłkę."
        )
    return True


def _zastosuj_uzytkownika(uzytkownik, login_lokalny, raport):
    from bpp.models import BppUser

    login = login_lokalny or uzytkownik.get("username")
    if not uzytkownik.get("istnieje", True):
        raport.append(
            f"UWAGA: na serwerze nie ma użytkownika {uzytkownik.get('username')!r} "
            "— tokenu użytkownika nie przeniesiono."
        )
        return
    token = uzytkownik.get("pbn_token") or ""
    if not token:
        raport.append(
            f"UWAGA: użytkownik {uzytkownik.get('username')!r} nie ma na serwerze "
            "tokenu PBN (albo serwer nie potrafi go odszyfrować) — zaloguj się "
            "do PBN lokalnie: bin/pbn-zaloguj-lokalnie.py."
        )
        return
    lokalny = BppUser.objects.filter(username=login).first()
    if lokalny is None:
        raport.append(
            f"UWAGA: w lokalnej bazie nie ma użytkownika {login!r} — tokenu "
            "użytkownika nie zapisano."
        )
        return
    surowa_data = uzytkownik.get("pbn_token_updated")
    lokalny.pbn_token = token
    lokalny.pbn_token_updated = parse_datetime(surowa_data) if surowa_data else None
    # update_fields + pominięcie pbn_api.autoryzacja.zapisz_token: przeniesienie
    # tokenu NIE jest „zalogowaniem" i nie może ruszyć kolejki eksportu.
    lokalny.save(update_fields=["pbn_token", "pbn_token_updated"])
    raport.append(
        f"Token PBN użytkownika {login}: zapisany (na serwerze ustawiony "
        f"{surowa_data or 'w nieznanym terminie'})."
    )


def zastosuj(dane: dict, skrot=None, login_lokalny=None) -> list[str]:
    """Zapisuje pobraną konfigurację w lokalnej bazie (szyfrując lokalnym
    kluczem). Zwraca raport — bez żadnych sekretów."""
    if dane.get("blad"):
        raise BladPrzenoszenia(f"Serwer zgłosił błąd: {dane['blad']}.")

    raport = []
    pary = _dopasuj_uczelnie(dane.get("uczelnie") or [], skrot)
    zapisane = [_zastosuj_uczelnie(u, z, raport) for u, z in pary]
    if not any(zapisane):
        raise BladPrzenoszenia(
            "Nie zapisano konfiguracji aplikacji PBN dla żadnej uczelni — "
            + (
                " ".join(raport)
                if raport
                else "skróty uczelni na serwerze i w lokalnej bazie się nie pokrywają."
            )
        )

    if dane.get("uzytkownik"):
        _zastosuj_uzytkownika(dane["uzytkownik"], login_lokalny, raport)
    return raport
