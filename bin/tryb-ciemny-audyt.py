#!/usr/bin/env python
"""Audyt trybu ciemnego: szuka „białych plam” i nieczytelnego tekstu.

Otwiera strony BPP w Playwright z ``color_scheme="dark"`` i dla każdej
strony raportuje:

* **plamy** — widoczne elementy większe niż 40×40 px, których wyliczone
  tło (``background-color`` albo kolor z gradientu w ``background-image``)
  ma luminancję względną powyżej progu (domyślnie 0.8),
* **kontrast** — elementy z własnym tekstem (także tekst SVG — `fill`), których kolor tekstu ma
  współczynnik kontrastu z efektywnym tłem poniżej 4.5:1 (3:1 dla dużego
  tekstu) — próg WCAG AA.

Dodatkowo najeżdża myszą na pierwszy wiersz kilku tabel i mierzy go
w stanie ``:hover`` (wpisy z prefiksem ``HOVER``). Tło wykresów SVG
(``rect`` z jasnym ``fill``) liczy się jako plama. Zawartości ``<canvas>``
skrypt nie ocenia (piksele zależą od biblioteki rysującej).

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
    ("metryki-statystyki", "/ewaluacja_metryki/statystyki/"),
    ("metryki-kola", "/ewaluacja_metryki/?widok=kola"),
    ("metryki-pkdaut", "/ewaluacja_metryki/?widok=pkdaut"),
    ("metryki-mapa-ciepla", "/ewaluacja_metryki/?widok=mapa_ciepla"),
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

# Moduły spoza menu (osobne arkusze CSS, panele obsługi) — dla --moduly.
MODULY_DODATKOWE = [
    "/ewaluacja_dwudyscyplinowcy/",
    "/pbn_export_queue/",
    "/pbn_import/",
    "/pbn_downloader_app/",
    "/pbn-wysylka-oswiadczen/",
    "/komparator_pbn/",
    "/komparator-pbn-udzialy/",
    "/komparator-publikacji-pbn/",
    "/komparator-zrodel-pbn/",
    "/rozbieznosci_dyscyplin/",
    "/przemapuj-zrodla-pbn/",
    "/importer_autorow_pbn/",
    "/stan_systemu/",
    "/live/",
]

JS_LINKI_MENU = """() => [...document.querySelectorAll('#example-menu a[href]')]
  .map((a) => a.getAttribute('href'))"""


def wczytaj(page, adres):
    """goto z czekaniem na ciszę w sieci; strony z ciągłym połączeniem
    (SSE, odświeżanie postępu) nigdy jej nie osiągają — wtedy wystarczy
    `load`."""
    try:
        page.goto(adres, wait_until="networkidle", timeout=15000)
    except PlaywrightError as e:
        if "Download is starting" in str(e):
            return False  # link do pliku (np. XLSX), nie strona
        try:
            page.goto(adres, wait_until="load", timeout=30000)
        except PlaywrightError as e2:
            print(f"!! {adres}: {str(e2).splitlines()[0]}")
            return False
    page.wait_for_timeout(400)
    return True


def strony_modulow(page, baza):
    """Linki z menu (zalogowany admin) + MODULY_DODATKOWE: (nazwa, ścieżka)."""
    page.goto(baza + "/", wait_until="networkidle")
    sciezki = []
    for h in page.evaluate(JS_LINKI_MENU) + MODULY_DODATKOWE:
        h = re.sub(r"^https?://[^/]+", "", h or "").split("#")[0].split("?")[0]
        if not h.startswith("/") or h.startswith("/admin") or "logout" in h:
            continue
        if h.startswith("/bpp/konfigurator-wygladu"):
            continue  # samodzielna strona bez motywu (własny, jasny interfejs)
        if h not in sciezki:
            sciezki.append(h)
    return [("m:" + (h.strip("/").replace("/", "_") or "glowna"), h) for h in sciezki]


# Strony odkrywane z dodatkowym warunkiem: (nazwa, lista, regex, selektor,
# który musi być na stronie docelowej). Szczegóły metryki — autor z pracami
# wybranymi (wiersze tr.success); optymalizacja — link ze szczegółów.
STRONY_Z_WARUNKIEM = [
    (
        "metryki-szczegoly",
        "/ewaluacja_metryki/",
        r"^/ewaluacja_metryki/(?:[^/]+/)?szczegoly/[^/]+/[^/]+/$",
        "tr.success",
    ),
    (
        "optymalizuj-publikacje",
        "@metryki-szczegoly",
        r"^/ewaluacja_optymalizuj_publikacje/[^/?#]+/?$",
        None,
    ),
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


def odkryj_z_warunkiem(page, baza, lista, wzorzec, warunek, limit=15):
    page.goto(baza + lista, wait_until="networkidle")
    hrefy = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))"
    )
    kandydaci = []
    for h in hrefy:
        h = re.sub(r"^https?://[^/]+", "", h or "")
        if re.match(wzorzec, h) and h not in kandydaci:
            kandydaci.append(h)
    for h in kandydaci[:limit]:
        if warunek is None:
            return h
        page.goto(baza + h, wait_until="networkidle")
        if page.locator(warunek).count():
            return h
    return None


def audytuj(page, prog, min_rozmiar, korzen=None):
    return page.evaluate(JS_AUDYT, [prog, min_rozmiar, korzen])


# Wiersze tabel w stanie :hover — najeżdżamy myszą na pierwszy wiersz
# kilku pierwszych tabel i mierzymy tylko ten wiersz.
JS_OZNACZ_WIERSZE = """(ile) => {
  const wiersze = [];
  for (const t of document.querySelectorAll("table")) {
    const tr = [...t.querySelectorAll("tbody tr")].find(
      (w) => w.getBoundingClientRect().height > 0 && w.cells.length > 1);
    if (!tr) continue;
    tr.setAttribute("data-audyt-wiersz", String(wiersze.length));
    wiersze.push(wiersze.length);
    if (wiersze.length >= ile) break;
  }
  return wiersze;
}"""


def audytuj_hover(page, prog, ile=3):
    wynik = {"plamy": [], "kontrast": []}
    for i in page.evaluate(JS_OZNACZ_WIERSZE, ile):
        selektor = f'[data-audyt-wiersz="{i}"]'
        try:
            page.hover(selektor, timeout=2000)
        except PlaywrightError:
            continue  # wiersz przykryty (np. lepki nagłówek) — pomijamy
        page.wait_for_timeout(250)
        w = audytuj(page, prog, 20, selektor)
        for klucz in ("plamy", "kontrast"):
            for x in w[klucz]:
                x["element"] = "HOVER " + x["element"]
                wynik[klucz].append(x)
    page.mouse.move(0, 0)
    return wynik


def zbadaj(page, nazwa, sciezka, a, raport, wyjscie, full_page=True, hover=True):
    wynik = audytuj(page, a.prog, a.min_rozmiar)
    if hover:
        h = audytuj_hover(page, a.prog)
        wynik["plamy"] += h["plamy"]
        wynik["kontrast"] += h["kontrast"]
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
    p.add_argument(
        "--przelacznik",
        choices=["jasny", "ciemny"],
        help="wybór przełącznika trybu kolorów (localStorage) przed wczytaniem",
    )
    p.add_argument("--prog", type=float, default=0.8)
    p.add_argument("--min-rozmiar", type=int, default=40)
    p.add_argument("--strony", help="lista nazw stron po przecinku")
    p.add_argument("--scisle", action="store_true")
    p.add_argument(
        "--moduly",
        action="store_true",
        help="także strony z menu i moduły obsługi (MODULY_DODATKOWE)",
    )
    p.add_argument(
        "--tylko-moduly", action="store_true", help="tylko strony z --moduly"
    )
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

    def zbadaj(self, page, nazwa, sciezka, full_page=True, hover=True):
        zbadaj(
            page, nazwa, sciezka, self.a, self.raport, self.wyjscie, full_page, hover
        )

    def strony_z_warunkiem(self, page):
        wynik = []
        znalezione = {}
        for nazwa, lista, wzorzec, warunek in STRONY_Z_WARUNKIEM:
            if lista.startswith("@"):
                lista = znalezione.get(lista[1:])
                if not lista:
                    continue
            sciezka = odkryj_z_warunkiem(page, self.baza, lista, wzorzec, warunek)
            if sciezka:
                znalezione[nazwa] = sciezka
                if self.chce(nazwa):
                    wynik.append((nazwa, sciezka))
            else:
                print(f"!! nie znalazłem strony {nazwa} na {lista}")
        return wynik

    def strony(self, page):
        if self.a.tylko_moduly:
            for nazwa, sciezka in strony_modulow(page, self.baza):
                if wczytaj(page, self.baza + sciezka):
                    self.zbadaj(page, nazwa, sciezka)
            return
        strony = list(STRONY_STALE)
        if self.a.moduly:
            znane = {sc for _n, sc in strony}
            strony += [x for x in strony_modulow(page, self.baza) if x[1] not in znane]
        for nazwa, lista, wzorzec in STRONY_ODKRYWANE:
            if not self.chce(nazwa):
                continue
            sciezka = odkryj(page, self.baza, lista, wzorzec)
            if sciezka:
                strony.append((nazwa, sciezka))
            else:
                print(f"!! nie znalazłem strony {nazwa} na {lista}")
        strony += self.strony_z_warunkiem(page)
        for nazwa, sciezka in strony:
            if self.chce(nazwa) and wczytaj(page, self.baza + sciezka):
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
            self.zbadaj(page, nazwa, sciezka, full_page=False, hover=False)

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
        self.zbadaj(page, "menu", "/ (menu)", full_page=False, hover=False)

    def nowy_kontekst(self, przegladarka):
        kontekst = przegladarka.new_context(**self.opcje)
        if self.a.przelacznik:
            kontekst.add_init_script(
                f"window.localStorage.setItem('bpp-tryb-kolorow', "
                f"'{self.a.przelacznik}')"
            )
        return kontekst

    def logowanie(self, przegladarka):
        # Strona logowania — bez sesji.
        if not self.chce("logowanie"):
            return
        kontekst = self.nowy_kontekst(przegladarka)
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
        page = przebieg.nowy_kontekst(przegladarka).new_page()
        if token:
            page.goto(f"{baza}/__autologin__/?token={token}")
        przebieg.strony(page)
        if not a.tylko_moduly:
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
