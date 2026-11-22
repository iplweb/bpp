"""Kompilacja motywu z konfiguratora wyglądu po stronie serwera.

Kompiluje osobny, odizolowany serwis ``motyw-kompilator``
(``docker/motyw-kompilator/serwer.js``, obraz ``iplweb/bpp_motyw_kompilator``
w tej samej wersji co appserver). Wykonuje ten sam kod JS co podgląd
w przeglądarce, więc wynik jest identyczny. Appserver nie uruchamia
cudzego silnika JS: ewentualna dziura w kompilatorze zostaje w kontenerze
bez bazy, sekretów i internetu.

- Produkcja: ``BPP_MOTYW_KOMPILATOR_URL`` (np. ``http://motyw-kompilator:8095``).
- Dev i testy (bez ustawionego URL-a): jednorazowe ``node serwer.js
  --jednorazowo`` na plikach z ``src/`` (wymaga Node'a i zbudowanych assetów).

Używane przy „Zastosuj” i przy migracji wyglądu (``manage.py odswiez_motywy``).
"""

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import requests
from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.templatetags.static import static

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
    """Sprawdzenia bez kompilatora (typ, obrazki). Pełna: motyw-konfig.js."""
    if not isinstance(konfig, dict):
        raise BladKompilacjiMotywu("Ustawienia muszą być obiektem JSON.")
    for pole, opis, limit in OBRAZY:
        obraz = konfig.get(pole, "")
        if not obraz:
            continue
        if not isinstance(obraz, str) or not RE_OBRAZ.match(obraz):
            raise BladKompilacjiMotywu(
                f"{opis}: dozwolone są tylko obrazki PNG, JPG, WebP, GIF i SVG."
            )
        if len(obraz) > limit:
            raise BladKompilacjiMotywu(f"{opis}: obrazek jest za duży.")


def _z_serwisu(url, dane):
    try:
        odp = requests.post(
            url.rstrip("/") + "/kompiluj", json=dane, timeout=LIMIT_CZASU_S
        )
    except requests.RequestException as e:
        raise KompilatorNiedostepny(
            f"Kompilator motywów jest niedostępny ({e.__class__.__name__})."
        ) from e
    if odp.status_code == 200:
        return odp.text
    try:
        blad = odp.json()
    except ValueError:
        blad = {}
    raise BladKompilacjiMotywu(
        blad.get("blad") or f"Kompilator motywów zwrócił błąd {odp.status_code}.",
        bledy=blad.get("bledy"),
    )


def _z_node(dane):
    node = shutil.which("node")
    js = finders.find("bpp/js/motyw-konfig.js")
    dist = finders.find("bpp/js/dist/motyw-zrodla-scss.json")
    if not node or not js or not dist or not SKRYPT_DEV.exists():
        raise KompilatorNiedostepny(
            "Kompilator motywów jest niedostępny: ustaw BPP_MOTYW_KOMPILATOR_URL "
            "albo (dev) zainstaluj Node i zbuduj assety (make assets)."
        )
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
        return wynik.stdout
    try:
        blad = json.loads(wynik.stderr)
    except ValueError:
        blad = {"blad": wynik.stderr.strip().splitlines()[-1:] or ["?"]}
        blad["blad"] = "Kompilacja motywu nie powiodła się: " + blad["blad"][0]
    raise BladKompilacjiMotywu(blad.get("blad"), bledy=blad.get("bledy"))


KLUCZ_BLOKADY = "bpp:motyw_kompilator:blokada"


def kompiluj(konfig, czekaj_s=0):
    """Ustawienia motywu → gotowy CSS. Rzuca BladKompilacjiMotywu.

    Naraz najwyżej JEDNA kompilacja na całą instalację (blokada w cache,
    wspólna dla wszystkich procesów appservera): bez tego kilkanaście
    równoległych „Zastosuj” trzymałoby tyle samo procesów czekających na
    kompilator. ``czekaj_s`` — ile czekać na wolną blokadę (migracja
    wyglądu czeka; „Zastosuj” od razu zgłasza zajętość).
    """
    wstepna_walidacja(konfig)
    dane = {"konfig": konfig, "czcionkiUrl": static("bpp/fonts").rstrip("/")}

    koniec = time.monotonic() + czekaj_s
    while not cache.add(KLUCZ_BLOKADY, 1, timeout=LIMIT_CZASU_S + 10):
        if time.monotonic() >= koniec:
            raise KompilatorZajety("Trwa budowanie innego motywu — spróbuj za chwilę.")
        time.sleep(1)
    try:
        url = getattr(settings, "BPP_MOTYW_KOMPILATOR_URL", "")
        if url:
            return _z_serwisu(url, dane)
        return _z_node(dane)
    finally:
        cache.delete(KLUCZ_BLOKADY)


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
