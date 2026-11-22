#!/usr/bin/env python
"""Audyt trybu ciemnego: szuka „białych plam” i nieczytelnego tekstu.

Otwiera strony BPP w Playwright z ``color_scheme="dark"`` i dla każdej
strony raportuje:

* **plamy** — widoczne elementy większe niż 40×40 px, których wyliczone
  tło (``background-color`` albo kolor z gradientu w ``background-image``)
  ma luminancję względną powyżej progu (domyślnie 0.8),
* **kontrast** — elementy z własnym tekstem, których kolor tekstu ma
  współczynnik kontrastu z efektywnym tłem poniżej 4.5:1 (3:1 dla dużego
  tekstu) — próg WCAG AA.

Użycie (z działającym ``run-site``, motyw uczelni ustawiony np. na
``app-blue-ciemny``)::

    uv run python bin/tryb-ciemny-audyt.py --wyjscie /tmp/audyt
    uv run python bin/tryb-ciemny-audyt.py --mobile --strony autorzy,autor

Port i token autologinu czyta z ``.dev_helpers_port``/``.dev_helpers_token``
w korzeniu repo (albo z ``--url``/``--token``). Kod zwrotu 1, gdy znaleziono
plamy (``--scisle`` — także przy problemach z kontrastem).
"""

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

KORZEN = Path(__file__).resolve().parent.parent

# Skrypt wykonywany w przeglądarce. Zwraca {plamy: [...], kontrast: [...]}.
# JS audytu jest wspólny z testem (src/bpp/tests/tryb_ciemny_audyt_js.py).
# Wczytywany wprost z pliku — import pakietu bpp.tests wymagałby Django.
_PLIK_JS = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "bpp"
    / "tests"
    / "tryb_ciemny_audyt_js.py"
)
_spec = importlib.util.spec_from_file_location("tryb_ciemny_audyt_js", _PLIK_JS)
_modul = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_modul)
JS_AUDYT = _modul.JS_AUDYT

# Strony stałe: (nazwa, ścieżka).
STRONY_STALE = [
    ("glowna", "/"),
    ("autorzy", "/bpp/autorzy/"),
    ("autorzy-litera", "/bpp/autorzy/?literka=A"),
    ("jednostki", "/bpp/jednostki/"),
    ("wydzialy", "/bpp/wydzialy/"),
    ("zrodla", "/bpp/zrodla/"),
    ("wydawcy", "/bpp/wydawcy/"),
    ("lata", "/bpp/lata/"),
    ("multiseek", "/multiseek/"),
    ("multiseek-wyniki", "/multiseek/results/"),
    ("raport-autorow", "/nowe_raporty/raport-autorow/"),
    ("raport-slotow", "/raport_slotow/raport-slotow-uczelnia/"),
    ("ranking-autorow", "/bpp/raporty/ranking-autorow/wybierz/"),
    ("ewaluacja-metryki", "/ewaluacja_metryki/"),
    ("zgloszenie", "/zglos_publikacje/nowe_zgloszenie/"),
]

# Strony szczegółów odkrywane z list: (nazwa, lista, regex odnośnika).
STRONY_ODKRYWANE = [
    ("autor", "/bpp/autorzy/?literka=A", r"^/bpp/autor/[^/]+/$"),
    ("jednostka", "/bpp/jednostki/", r"^/bpp/jednostka/[^/]+/$"),
    ("zrodlo", "/bpp/zrodla/", r"^/bpp/zrodlo/[^/]+/$"),
    ("wydawca", "/bpp/wydawcy/", r"^/bpp/wydawca/[^/]+/$"),
    ("rok", "/bpp/lata/", r"^/bpp/rok/\d+/$"),
    ("publikacja", "/multiseek/results/", r"^/bpp/rekord/"),
]


def odkryj(page, baza, lista, wzorzec):
    page.goto(baza + lista, wait_until="networkidle")
    hrefy = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))"
    )
    for h in hrefy:
        h = re.sub(r"^https?://[^/]+", "", h or "")
        if re.match(wzorzec, h):
            return h
    return None


def audytuj(page, prog, min_rozmiar):
    return page.evaluate(JS_AUDYT, [prog, min_rozmiar])


def zbadaj(page, nazwa, sciezka, a, raport, wyjscie, full_page=True):
    wynik = audytuj(page, a.prog, a.min_rozmiar)
    raport[nazwa] = {"sciezka": sciezka, **wynik}
    print(
        f"{nazwa:20s} plamy={len(wynik['plamy']):3d} "
        f"kontrast={len(wynik['kontrast']):3d}  {sciezka}"
    )
    if a.szczegoly:
        for x in wynik["plamy"][:15]:
            print(f"    PLAMA {x['element']} {x['rozmiar']} {x['tlo']}")
        for x in wynik["kontrast"][:15]:
            print(
                f"    KONTR {x['kontrast']:5} {x['element']} "
                f"{x['kolor']} na {x['tlo']} «{x['tekst']}»"
            )
    if wyjscie:
        page.screenshot(path=str(wyjscie / f"{nazwa}.png"), full_page=full_page)


def _globalna_wyszukiwarka(page):
    page.keyboard.press("/")
    page.wait_for_timeout(400)
    page.keyboard.type("Ger", delay=80)
    page.wait_for_timeout(1500)


def _autocomplete(page):
    page.locator(".select2-selection").first.click()
    page.wait_for_timeout(300)
    page.keyboard.type("a", delay=80)
    page.wait_for_timeout(1500)


# Stany wymagające interakcji: (nazwa, ścieżka, funkcja).
INTERAKCJE = [
    ("wyszukiwarka-globalna", "/", _globalna_wyszukiwarka),
    ("autocomplete", "/nowe_raporty/raport-autorow/", _autocomplete),
]


def argumenty():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--url", help="adres BPP (domyślnie z .dev_helpers_port)")
    p.add_argument("--token", help="token autologinu (z .dev_helpers_token)")
    p.add_argument("--anonim", action="store_true", help="bez logowania")
    p.add_argument("--wyjscie", default=None, help="katalog na zrzuty i raport")
    p.add_argument("--mobile", action="store_true", help="wąski ekran 390×844")
    p.add_argument("--jasny", action="store_true", help="color_scheme=light")
    p.add_argument("--prog", type=float, default=0.8)
    p.add_argument("--min-rozmiar", type=int, default=40)
    p.add_argument("--strony", help="lista nazw stron po przecinku")
    p.add_argument("--scisle", action="store_true")
    p.add_argument("--szczegoly", action="store_true", help="wypisz elementy")
    return p.parse_args()


def baza_i_token(a):
    baza = a.url
    if not baza:
        baza = "http://localhost:" + (KORZEN / ".dev_helpers_port").read_text().strip()
    token = a.token
    if not token and not a.anonim:
        plik = KORZEN / ".dev_helpers_token"
        token = plik.read_text().strip() if plik.exists() else None
    return baza.rstrip("/"), token


class Przebieg:
    """Jeden przebieg audytu: przeglądarka, wybrane strony, zebrany raport."""

    def __init__(self, a, baza, wyjscie):
        self.a = a
        self.baza = baza
        self.wyjscie = wyjscie
        self.wybrane = set(a.strony.split(",")) if a.strony else None
        self.raport = {}
        self.opcje = {
            "color_scheme": "light" if a.jasny else "dark",
            "viewport": {"width": 390, "height": 844}
            if a.mobile
            else {"width": 1366, "height": 900},
        }

    def chce(self, nazwa):
        return not self.wybrane or nazwa in self.wybrane

    def zbadaj(self, page, nazwa, sciezka, full_page=True):
        zbadaj(page, nazwa, sciezka, self.a, self.raport, self.wyjscie, full_page)

    def strony(self, page):
        strony = list(STRONY_STALE)
        for nazwa, lista, wzorzec in STRONY_ODKRYWANE:
            if not self.chce(nazwa):
                continue
            sciezka = odkryj(page, self.baza, lista, wzorzec)
            if sciezka:
                strony.append((nazwa, sciezka))
            else:
                print(f"!! nie znalazłem strony {nazwa} na {lista}")
        for nazwa, sciezka in strony:
            if self.chce(nazwa):
                page.goto(self.baza + sciezka, wait_until="networkidle")
                page.wait_for_timeout(400)
                self.zbadaj(page, nazwa, sciezka)

    def interakcje(self, page):
        # Okno globalnego wyszukiwania i rozwinięty autocomplete.
        for nazwa, sciezka, akcja in INTERAKCJE:
            if not self.chce(nazwa):
                continue
            page.goto(self.baza + sciezka, wait_until="networkidle")
            try:
                akcja(page)
            except PlaywrightError as e:
                print(f"!! {nazwa}: interakcja nie powiodła się: {e}")
                continue
            page.wait_for_timeout(800)
            self.zbadaj(page, nazwa, sciezka, full_page=False)

    def menu(self, page):
        # Rozwinięte menu górne (na telefonie — hamburger).
        if not self.chce("menu"):
            return
        page.goto(self.baza + "/", wait_until="networkidle")
        if self.a.mobile:
            element = page.locator("[data-toggle], .menu-icon").first
            if element.count():
                element.click()
        else:
            element = page.locator(".top-bar .is-dropdown-submenu-parent").first
            if element.count():
                element.hover()
        page.wait_for_timeout(500)
        self.zbadaj(page, "menu", "/ (menu)", full_page=False)

    def logowanie(self, przegladarka):
        # Strona logowania — bez sesji.
        if not self.chce("logowanie"):
            return
        kontekst = przegladarka.new_context(**self.opcje)
        page = kontekst.new_page()
        page.goto(self.baza + "/accounts/login/", wait_until="networkidle")
        self.zbadaj(page, "logowanie", "/accounts/login/")
        kontekst.close()


def main():
    a = argumenty()
    baza, token = baza_i_token(a)
    wyjscie = Path(a.wyjscie) if a.wyjscie else None
    if wyjscie:
        wyjscie.mkdir(parents=True, exist_ok=True)

    przebieg = Przebieg(a, baza, wyjscie)
    with sync_playwright() as pw:
        przegladarka = pw.chromium.launch()
        page = przegladarka.new_context(**przebieg.opcje).new_page()
        if token:
            page.goto(f"{baza}/__autologin__/?token={token}")
        przebieg.strony(page)
        przebieg.interakcje(page)
        przebieg.menu(page)
        przebieg.logowanie(przegladarka)
        przegladarka.close()

    raport = przebieg.raport
    plamy = sum(len(v["plamy"]) for v in raport.values())
    kontr = sum(len(v["kontrast"]) for v in raport.values())
    print(f"RAZEM: plamy={plamy} kontrast={kontr} (stron: {len(raport)})")
    if wyjscie:
        (wyjscie / "raport.json").write_text(
            json.dumps(raport, ensure_ascii=False, indent=2)
        )
    if plamy or (a.scisle and kontr):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
