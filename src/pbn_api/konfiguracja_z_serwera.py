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
_skrot = %(skrot)r
_wynik = {"wersja": 1, "blad": None, "uzytkownik": None}
_uczelnie = list(Uczelnia.objects.order_by("pk"))
_uczelnia = None
if _skrot:
    for _u in _uczelnie:
        if _u.skrot == _skrot:
            _uczelnia = _u
    if _uczelnia is None:
        _wynik["blad"] = "na serwerze nie ma uczelni o skrocie " + repr(_skrot)
elif len(_uczelnie) == 1:
    _uczelnia = _uczelnie[0]
elif not _uczelnie:
    _wynik["blad"] = "na serwerze nie ma zadnej uczelni"
else:
    _skroty = []
    for _u in _uczelnie:
        _skroty.append(str(_u.skrot))
    _wynik["blad"] = (
        "na serwerze jest kilka uczelni, wskaz jedna (--uczelnia-zdalna): "
        + ", ".join(_skroty)
    )
if _uczelnia is not None:
    _wynik["uczelnia_skrot"] = str(_uczelnia.skrot)
    _wynik["pbn_api_root"] = str(_uczelnia.pbn_api_root or "")
    _wynik["pbn_app_name"] = str(_uczelnia.pbn_app_name or "")
    _wynik["pbn_app_token"] = str(_uczelnia.pbn_app_token or "")
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


def zdalny_skrypt(login=None, skrot=None) -> str:
    return ZDALNY_SKRYPT % {
        "login": login or "",
        "skrot": skrot or "",
        "znacznik": ZNACZNIK,
    }


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
    skrot=None,
    remote_deploy_path="~/bpp-deploy",
    remote_compose_service="appserver",
) -> str:
    """Polecenie powłoki dla serwera. Nie zawiera żadnych sekretów."""
    return (
        f"cd {_zacytuj_sciezke_zdalna(remote_deploy_path)} && "
        f"docker compose exec -T {shlex.quote(remote_compose_service)} "
        f"python src/manage.py shell -c {shlex.quote(zdalny_skrypt(login, skrot))}"
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
    skrot=None,
    remote_deploy_path="~/bpp-deploy",
    remote_compose_service="appserver",
    timeout=120,
) -> dict:
    polecenie = zdalne_polecenie(
        login, skrot, remote_deploy_path, remote_compose_service
    )
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


def _wybierz_uczelnie_lokalna(skrot_lokalny, skrot_zdalny):
    from bpp.models import Uczelnia

    uczelnie = list(Uczelnia.objects.order_by("pk"))
    if not uczelnie:
        raise BladPrzenoszenia("W lokalnej bazie nie ma żadnej uczelni.")
    for kandydat in (skrot_lokalny, skrot_zdalny):
        if not kandydat:
            continue
        for u in uczelnie:
            if u.skrot == kandydat:
                return u
        if kandydat == skrot_lokalny:
            raise BladPrzenoszenia(
                f"W lokalnej bazie nie ma uczelni o skrócie {skrot_lokalny!r}."
            )
    if len(uczelnie) == 1:
        return uczelnie[0]
    lista = ", ".join(str(u.skrot) for u in uczelnie)
    raise BladPrzenoszenia(
        f"W lokalnej bazie jest kilka uczelni — wskaż jedną (--uczelnia): {lista}"
    )


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


def zastosuj(dane: dict, skrot_lokalny=None, login_lokalny=None) -> list[str]:
    """Zapisuje pobraną konfigurację w lokalnej bazie (szyfrując lokalnym
    kluczem). Zwraca raport — bez żadnych sekretów."""
    if dane.get("blad"):
        raise BladPrzenoszenia(f"Serwer zgłosił błąd: {dane['blad']}.")

    root = (dane.get("pbn_api_root") or "").rstrip("/")
    nazwa = dane.get("pbn_app_name") or ""
    token = dane.get("pbn_app_token") or ""
    if urlsplit(root).scheme not in ("http", "https"):
        raise BladPrzenoszenia("Serwer nie zwrócił poprawnego adresu API PBN.")
    if not nazwa or not token:
        raise BladPrzenoszenia(
            "Serwer nie zwrócił nazwy lub tokenu aplikacji PBN — uczelnia na "
            "serwerze nie ma skonfigurowanej integracji z PBN albo serwer sam "
            "nie potrafi odszyfrować tokenu (sprawdź tam `manage.py check`, "
            "bpp.W103)."
        )

    uczelnia = _wybierz_uczelnie_lokalna(skrot_lokalny, dane.get("uczelnia_skrot"))
    uczelnia.pbn_api_root = root
    uczelnia.pbn_app_name = nazwa
    uczelnia.pbn_app_token = token
    pola = ["pbn_api_root", "pbn_app_name", "pbn_app_token"]
    raport = []
    if not uczelnia.pbn_integracja:
        uczelnia.pbn_integracja = True
        pola.append("pbn_integracja")
        raport.append("Włączono „Czy używać integracji z PBN?” (pbn_integracja).")
    try:
        uczelnia.save(update_fields=pola)
    except ValidationError as e:
        # Uczelnia.save() woła clean() — m.in. odrzuca adres API wskazujący
        # na sieć prywatną. Komunikaty walidacji nie zawierają sekretów.
        raise BladPrzenoszenia(
            f"Lokalna uczelnia {uczelnia.skrot} nie przechodzi walidacji przy "
            f"zapisie: {'; '.join(e.messages)}"
        ) from e
    raport.insert(
        0,
        f"Konfiguracja aplikacji PBN uczelni {uczelnia.skrot}: zapisana "
        f"(adres API {root}, aplikacja {nazwa}, token aplikacji zaszyfrowany "
        "lokalnym kluczem).",
    )
    if not uczelnia.pbn_aktualizuj_na_biezaco:
        raport.append(
            "Przyciski „Zapisz i wyślij do PBN” są wyłączone "
            "(pbn_aktualizuj_na_biezaco) — włącz w adminie uczelni, jeśli "
            "chcesz testować ręczną wysyłkę."
        )

    if dane.get("uzytkownik"):
        _zastosuj_uzytkownika(dane["uzytkownik"], login_lokalny, raport)
    return raport
