"""Kompilacja motywu z konfiguratora wyglądu po stronie serwera.

Kompiluje osobny, odizolowany serwis ``motyw-kompilator``
(``docker/motyw-kompilator/serwer.js``, obraz ``iplweb/bpp_motyw_kompilator``
w tej samej wersji co appserver). Wykonuje ten sam kod JS co podgląd
w przeglądarce, więc wynik jest identyczny. Appserver nie uruchamia
cudzego silnika JS: ewentualna dziura w kompilatorze zostaje w kontenerze
bez bazy, sekretów i internetu.

- Produkcja i CI: ``BPP_MOTYW_KOMPILATOR_URL`` (np.
  ``http://motyw-kompilator:8095``).
- Dev (bez ustawionego URL-a): jednorazowe ``node serwer.js --jednorazowo``
  na plikach z ``src/`` (wymaga Node'a i zbudowanych assetów).

Widoki używają ``skompiluj()`` (zwraca ``WynikKompilacji`` — komunikaty dla
użytkownika składane jawnie, szczegóły błędów tylko w logu). ``kompiluj()``
rzuca wyjątki — dla komendy ``odswiez_motywy`` i kodu bez HTTP.
"""

import json
import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests
from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.templatetags.static import static

logger = logging.getLogger(__name__)

LIMIT_CZASU_S = 120

# Jak MAKS_DLUGOSC_OBRAZU w motyw-konfig.js — tu tylko wstępne odsianie przed
# wysłaniem do kompilatora (pełną walidację robi motyw-konfig.js).
MAKS_DLUGOSC_OBRAZU = 700 * 1024
RE_OBRAZ = re.compile(
    r"^data:image/(png|jpeg|webp|gif|svg\+xml);base64,[A-Za-z0-9+/=]+$"
)

SKRYPT_DEV = (
    Path(__file__).resolve().parent.parent.parent
    / "docker"
    / "motyw-kompilator"
    / "serwer.js"
)

NIEDOSTEPNY = "Kompilator motywów jest teraz niedostępny."
ZAJETY = "Trwa budowanie innego motywu — spróbuj za chwilę."
NIEUDANA = "Kompilacja motywu nie powiodła się — szczegóły w logu serwera."

# Rodzaje wyniku.
OK = "ok"
NIEPOPRAWNE = "niepoprawne"  # ustawienia odrzucone (walidacja)
BRAK_KOMPILATORA = "niedostepny"
KOLEJKA = "zajety"
BLAD = "blad"


@dataclass
class WynikKompilacji:
    css: str | None = None
    rodzaj: str = OK
    blad: str = ""
    bledy: list = field(default_factory=list)

    @property
    def ok(self):
        return self.rodzaj == OK


class BladKompilacjiMotywu(Exception):
    """Ustawienia niepoprawne albo kompilacja się nie udała (komunikat po polsku)."""

    def __init__(self, komunikat, bledy=None):
        super().__init__(komunikat)
        self.bledy = bledy or []


class KompilatorNiedostepny(BladKompilacjiMotywu):
    """Kompilator nie działa — konfigurator proponuje zapisanie motywu."""


class KompilatorZajety(BladKompilacjiMotywu):
    """Trwa inna kompilacja — widok odpowiada 429 (nie 503: nginx w bpp-deploy
    zamienia 503 na stronę „przerwa techniczna”)."""


# (pole, opis, limit długości data URL) — jak w SCHEMAT motyw-konfig.js.
OBRAZY = (
    ("tlo_obraz", "Grafika w tle", MAKS_DLUGOSC_OBRAZU),
    ("logo_uczelni", "Logo uczelni", 200 * 1024),
)


def wstepna_walidacja(konfig):
    """Sprawdzenia bez kompilatora (typ, obrazki). Pełna: motyw-konfig.js.

    Zwraca komunikat błędu albo None.
    """
    if not isinstance(konfig, dict):
        return "Ustawienia muszą być obiektem JSON."
    for pole, opis, limit in OBRAZY:
        obraz = konfig.get(pole, "")
        if not obraz:
            continue
        if not isinstance(obraz, str) or not RE_OBRAZ.match(obraz):
            return f"{opis}: dozwolone są tylko obrazki PNG, JPG, WebP, GIF i SVG."
        if len(obraz) > limit:
            return f"{opis}: obrazek jest za duży."
    return None


def _odpowiedz_kompilatora(status, tresc_bledu):
    """Odpowiedź z błędem (serwis albo tryb jednorazowy) → wynik.

    400 = ustawienia odrzucone przez motyw-konfig.js: komunikat i lista błędów
    pochodzą z walidacji (teksty dla użytkownika). Inne błędy — szczegóły
    tylko do logu, użytkownik dostaje ogólny komunikat.
    """
    try:
        dane = json.loads(tresc_bledu)
    except ValueError:
        dane = {}
    if status == 400 and isinstance(dane, dict) and dane.get("bledy"):
        return WynikKompilacji(
            rodzaj=NIEPOPRAWNE,
            blad=" ".join(str(b.get("komunikat", "")) for b in dane["bledy"]),
            bledy=dane["bledy"],
        )
    logger.error("Kompilator motywów: błąd %s: %s", status, tresc_bledu[:2000])
    return WynikKompilacji(rodzaj=BLAD, blad=NIEUDANA)


def _z_serwisu(url, dane):
    try:
        odp = requests.post(
            url.rstrip("/") + "/kompiluj", json=dane, timeout=LIMIT_CZASU_S
        )
    except requests.RequestException:
        logger.warning("Kompilator motywów niedostępny pod %s", url, exc_info=True)
        return WynikKompilacji(rodzaj=BRAK_KOMPILATORA, blad=NIEDOSTEPNY)
    if odp.status_code == 200:
        return WynikKompilacji(css=odp.text)
    return _odpowiedz_kompilatora(odp.status_code, odp.text)


def _z_node(dane):
    node = shutil.which("node")
    js = finders.find("bpp/js/motyw-konfig.js")
    dist = finders.find("bpp/js/dist/motyw-zrodla-scss.json")
    if not node or not js or not dist or not SKRYPT_DEV.exists():
        logger.warning(
            "Kompilator motywów niedostępny: brak BPP_MOTYW_KOMPILATOR_URL, "
            "a lokalnie brak Node'a albo zbudowanych assetów (make assets)."
        )
        return WynikKompilacji(rodzaj=BRAK_KOMPILATORA, blad=NIEDOSTEPNY)
    wynik = subprocess.run(
        [node, str(SKRYPT_DEV), "--jednorazowo"],
        input=json.dumps(dane),
        capture_output=True,
        text=True,
        timeout=LIMIT_CZASU_S,
        env={
            "PATH": str(Path(node).parent),
            "BPP_MOTYW_JS": str(Path(js).parent),
            "BPP_MOTYW_DIST": str(Path(dist).parent),
        },
        check=False,
    )
    if wynik.returncode == 0:
        return WynikKompilacji(css=wynik.stdout)
    # Tryb jednorazowy: błąd walidacji = JSON z listą błędów (jak 400 serwisu).
    return _odpowiedz_kompilatora(400, wynik.stderr)


KLUCZ_BLOKADY = "bpp:motyw_kompilator:blokada"


def skompiluj(konfig, czekaj_s=0):
    """Ustawienia motywu → ``WynikKompilacji`` (bez wyjątków).

    Naraz najwyżej JEDNA kompilacja na całą instalację (blokada w cache,
    wspólna dla wszystkich procesów appservera): bez tego kilkanaście
    równoległych „Zastosuj” trzymałoby tyle samo procesów czekających na
    kompilator. ``czekaj_s`` — ile czekać na wolną blokadę (migracja
    wyglądu czeka; „Zastosuj” od razu zgłasza zajętość).
    """
    blad = wstepna_walidacja(konfig)
    if blad:
        return WynikKompilacji(rodzaj=NIEPOPRAWNE, blad=blad)
    dane = {"konfig": konfig, "czcionkiUrl": static("bpp/fonts").rstrip("/")}

    koniec = time.monotonic() + czekaj_s
    while not cache.add(KLUCZ_BLOKADY, 1, timeout=LIMIT_CZASU_S + 10):
        if time.monotonic() >= koniec:
            return WynikKompilacji(rodzaj=KOLEJKA, blad=ZAJETY)
        time.sleep(1)
    try:
        url = getattr(settings, "BPP_MOTYW_KOMPILATOR_URL", "")
        if url:
            return _z_serwisu(url, dane)
        return _z_node(dane)
    finally:
        cache.delete(KLUCZ_BLOKADY)


def kompiluj(konfig, czekaj_s=0):
    """Jak ``skompiluj``, ale zwraca CSS albo rzuca BladKompilacjiMotywu."""
    wynik = skompiluj(konfig, czekaj_s=czekaj_s)
    if wynik.ok:
        return wynik.css
    klasa = {
        BRAK_KOMPILATORA: KompilatorNiedostepny,
        KOLEJKA: KompilatorZajety,
    }.get(wynik.rodzaj, BladKompilacjiMotywu)
    raise klasa(wynik.blad, bledy=wynik.bledy)


def czekaj_na_kompilator(limit_s=90, odstep_s=2):
    """Czeka, aż serwis kompilatora odpowie (start kontenerów jest równoległy).

    Bez ustawionego URL-a (dev: lokalny Node) od razu True.
    """
    url = getattr(settings, "BPP_MOTYW_KOMPILATOR_URL", "")
    if not url:
        return True
    koniec = time.monotonic() + limit_s
    while True:
        try:
            if requests.get(url.rstrip("/") + "/zdrowie", timeout=5).status_code == 200:
                return True
        except requests.RequestException:
            pass  # jeszcze nie wstał — próbujemy dalej do limitu czasu
        if time.monotonic() >= koniec:
            return False
        time.sleep(odstep_s)


def kompilator_dostepny():
    """Czy da się teraz zbudować motyw (szybki test, do 2 s)."""
    url = getattr(settings, "BPP_MOTYW_KOMPILATOR_URL", "")
    if url:
        try:
            odp = requests.get(url.rstrip("/") + "/zdrowie", timeout=2)
        except requests.RequestException:
            return False
        return odp.status_code == 200
    return bool(
        shutil.which("node")
        and finders.find("bpp/js/dist/motyw-zrodla-scss.json")
        and SKRYPT_DEV.exists()
    )
