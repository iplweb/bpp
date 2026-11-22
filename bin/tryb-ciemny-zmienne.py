#!/usr/bin/env python
"""Zamienia jasne tła / ciemne teksty / jasne ramki na zmienne `--bpp-*`.

Dla stylów, które NIE trafiają do skompilowanego CSS motywu — bloki
``<style>`` w szablonach i osobne arkusze modułów (np.
``ewaluacja_optymalizuj_publikacje.css``). Takich reguł nie widzi ani
ręczny tryb ciemny (``_tryb-ciemny.scss``), ani konfigurator wyglądu
(``przetworzCss`` przetwarza tylko CSS motywu). Zmienna z oryginałem jako
wartością zapasową::

    background: #f8f9fa;   →   background: var(--bpp-tlo-pow-2, #f8f9fa);

W trybie jasnym zmienne nie są zdefiniowane, więc wygląd zostaje co do
piksela. W trybie ciemnym definiują je oba mechanizmy: mixin
``bpp-tryb-ciemny`` i ``przetworzCss`` (lista ``ZMIENNE_KOLOROW`` w
``motyw-konfig.js``). Pełna lista zmiennych: ``_tryb-ciemny.scss``.

Obsługuje zagnieżdżenia SCSS. Reguły z własnym ciemnym/nasyconym tłem
(przyciski) zostawia bez zmian tekstu, a plakietki (jasne barwne tło
z ciemnym tekstem) i gradienty z barwami (skale) — w całości.
Wynik trzeba przejrzeć (``git diff``).

Użycie::

    uv run python bin/tryb-ciemny-zmienne.py PLIK [PLIK ...]

Pliki ``.html`` — bloki ``<style>`` i atrybuty ``style="…"`` (bez
wartości z szablonu; ``--bez-inline`` pomija atrybuty).
"""

import argparse
import colorsys
import re
from pathlib import Path

import tinycss2
import tinycss2.color4

RE_KOLOR = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|\b(?:white|black|gray|grey|whitesmoke|green|red|blue|darkgreen|darkred|navy)\b"
)
RE_STYLE = re.compile(r"(<style[^>]*>)(.*?)(</style>)", re.S)
RE_INLINE = re.compile(r'(\sstyle=")([^"]*)(")')
RE_KOMENTARZ = re.compile(r"/\*.*?\*/|(?<![:\w])//[^\n]*", re.S)
# Tagi Django w szablonach (mają klamry) — maskujemy na czas przetwarzania.
RE_DJANGO = re.compile(r"\{%.*?%\}|\{\{.*?\}\}|\{#.*?#\}")

TLA = ("background", "background-color", "background-image")
RAMKI = (
    "border",
    "border-color",
    "border-top",
    "border-bottom",
    "border-left",
    "border-right",
    "border-top-color",
    "border-bottom-color",
    "border-left-color",
    "border-right-color",
)


def rgb(tekst):
    try:
        c = tinycss2.color4.parse_color(tekst)
    except (ValueError, TypeError):
        return None
    if c is None or isinstance(c, str):
        return None
    r, g, b = c.to("srgb").coordinates
    return (r, g, b, 1 if c.alpha is None else c.alpha)


def luminancja(r, g, b):
    def f(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def odcien(r, g, b):
    h, s, _v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360, s


def wg_odcienia(h, prefiks, niebieski):
    if h < 20 or h >= 330:
        return f"{prefiks}-blad"
    if h < 65:
        return f"{prefiks}-ostrzezenie"
    if h < 170:
        return f"{prefiks}-sukces"
    return niebieski


def zmienna_tla(c, selektor):
    r, g, b, a = c
    if a < 0.9 or luminancja(r, g, b) <= 0.7:
        return None
    h, s = odcien(r, g, b)
    if s < 0.08:
        if ":hover" in selektor or ":focus" in selektor:
            return "--bpp-tlo-hover"
        return "--bpp-tlo-pow" if luminancja(r, g, b) >= 0.975 else "--bpp-tlo-pow-2"
    return wg_odcienia(h, "--bpp-tlo", "--bpp-tlo-info")


def zmienna_tekstu(c):
    r, g, b, a = c
    if a < 0.5 or luminancja(r, g, b) >= 0.3:
        return None
    h, s = odcien(r, g, b)
    if s < 0.6:
        return (
            "--bpp-tekst" if luminancja(r, g, b) < 0.08 else "--bpp-tekst-przygaszony"
        )
    return wg_odcienia(h, "--bpp-tekst", "--bpp-akcent")


def zmienna_ramki(c):
    r, g, b, a = c
    if a < 0.5 or luminancja(r, g, b) <= 0.55 or odcien(r, g, b)[1] >= 0.15:
        return None
    return "--bpp-ramka"


def ma_wlasne_tlo(deklaracje):
    """Ciemne albo nasycone tło w regule (przycisk, plakietka)."""
    for prop, wartosc in deklaracje:
        if prop not in TLA:
            continue
        for m in RE_KOLOR.finditer(wartosc):
            c = rgb(m.group(0))
            if c and c[3] >= 0.5:
                r, g, b, _a = c
                s = odcien(r, g, b)[1]
                if luminancja(r, g, b) < 0.5 or s > 0.5:
                    return True
    return False


def barwny(c):
    """Wyraźnie barwny (skala, plakietka) — nie pastelowe tło komunikatu."""
    r, g, b, _a = c
    return odcien(r, g, b)[1] > 0.25


def gradient_danych(wartosc):
    """Gradient z barwnym kolorem (skala „temperatury”, przycisk) — to
    informacja, nie tło pod treścią; zostaje bez zmian."""
    if "gradient" not in wartosc:
        return False
    for m in RE_KOLOR.finditer(wartosc):
        c = rgb(m.group(0))
        if c and (barwny(c) or luminancja(*c[:3]) <= 0.7):
            return True
    return False


def plakietka(deklaracje):
    """Jasne barwne tło + ciemny tekst w jednej regule (plakietka, etykieta
    skali) — czytelna także na ciemnej stronie, zostaje jak jest."""
    tlo = tekst = False
    for prop, wartosc in deklaracje:
        for m in RE_KOLOR.finditer(wartosc):
            c = rgb(m.group(0))
            if not c:
                continue
            if prop in TLA and barwny(c) and luminancja(*c[:3]) > 0.7:
                tlo = True
            if prop == "color" and luminancja(*c[:3]) < 0.3:
                tekst = True
    return tlo and tekst


def przepisz_wartosc(prop, wartosc, selektor, wlasne_tlo):
    if "var(" in wartosc or (prop in TLA and gradient_danych(wartosc)):
        return wartosc

    def zamien(m):
        c = rgb(m.group(0))
        if c is None:
            return m.group(0)
        if prop in TLA:
            nazwa = zmienna_tla(c, selektor)
        elif prop == "color" and not wlasne_tlo:
            nazwa = zmienna_tekstu(c)
        elif prop in RAMKI:
            nazwa = zmienna_ramki(c)
        else:
            nazwa = None
        return f"var({nazwa}, {m.group(0)})" if nazwa else m.group(0)

    return RE_KOLOR.sub(zamien, wartosc)


def _nazwa(prop):
    """Nazwa właściwości (bez masek komentarzy i wcięć przed nią)."""
    return prop.split()[-1].lower() if prop.split() else ""


def _deklaracje(tekst):
    wynik = []
    for cz in tekst.split(";"):
        if ":" in cz:
            prop, wartosc = cz.split(":", 1)
            wynik.append((_nazwa(prop), wartosc))
    return wynik


def _przepisz_deklaracje(tekst, selektor, wlasne):
    wynik = []
    for cz in tekst.split(";"):
        if ":" not in cz:
            wynik.append(cz)
            continue
        prop, wartosc = cz.split(":", 1)
        wynik.append(
            prop + ":" + przepisz_wartosc(_nazwa(prop), wartosc, selektor, wlasne)
        )
    return ";".join(wynik)


def _koniec_bloku(css, i):
    """Indeks `}` zamykającego `{` z pozycji i."""
    glebokosc = 0
    for j in range(i, len(css)):
        if css[j] == "{":
            glebokosc += 1
        elif css[j] == "}":
            glebokosc -= 1
            if glebokosc == 0:
                return j
    return len(css) - 1


def przetworz_cialo(css, selektor=""):
    """Treść bloku: własne deklaracje + zagnieżdżone bloki (SCSS)."""
    kawalki = []  # ("d", tekst) albo ("b", selektor, treść)
    bufor = ""
    i = 0
    while i < len(css):
        if css[i] == "{":
            k = max(bufor.rfind(";"), bufor.rfind("}"))
            kawalki.append(("d", bufor[: k + 1]))
            j = _koniec_bloku(css, i)
            kawalki.append(("b", bufor[k + 1 :], css[i + 1 : j]))
            bufor = ""
            i = j + 1
            continue
        bufor += css[i]
        i += 1
    kawalki.append(("d", bufor))

    wlasne_tekst = "".join(k[1] for k in kawalki if k[0] == "d")
    deklaracje = _deklaracje(wlasne_tekst)
    pomin = plakietka(deklaracje)
    wlasne = ma_wlasne_tlo(deklaracje) or any(
        p in TLA and gradient_danych(w) for p, w in deklaracje
    )
    wynik = []
    for k in kawalki:
        if k[0] == "d":
            wynik.append(
                k[1]
                if pomin or not selektor.strip()
                else _przepisz_deklaracje(k[1], selektor, wlasne)
            )
        else:
            pelny = (selektor + " " + k[1]).strip()
            wynik.append(k[1] + "{" + przetworz_cialo(k[2], pelny) + "}")
    return "".join(wynik)


def przepisz_css(css):
    maski = []

    def maskuj(m):
        maski.append(m.group(0))
        return f"\x00{len(maski) - 1}\x00"

    # Tagi Django i komentarze (mogą mieć `:` i `;`) — na czas przetwarzania
    # zamienione na znaczniki.
    css = RE_DJANGO.sub(maskuj, css)
    css = RE_KOMENTARZ.sub(maskuj, css)
    css = przetworz_cialo(css)
    for _ in range(2):  # komentarz mógł zawierać zamaskowany tag
        css = re.sub(r"\x00(\d+)\x00", lambda m: maski[int(m.group(1))], css)
    return css


def przepisz_inline(m):
    """Atrybut style="…" — deklaracje bez selektora (jak jedna reguła)."""
    css = m.group(2)
    if "{%" in css or "{{" in css:
        return m.group(0)  # wartości z szablonu — nie ruszamy
    return m.group(1) + przetworz_cialo(css, "[style]") + m.group(3)


def przepisz_plik(sciezka, inline=True):
    tekst = sciezka.read_text()
    if sciezka.suffix == ".html":
        nowy = RE_STYLE.sub(
            lambda m: m.group(1) + przepisz_css(m.group(2)) + m.group(3), tekst
        )
        if inline:
            nowy = RE_INLINE.sub(przepisz_inline, nowy)
    else:
        nowy = przepisz_css(tekst)
    if nowy != tekst:
        sciezka.write_text(nowy)
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("pliki", nargs="+", type=Path)
    parser.add_argument(
        "--bez-inline", action="store_true", help='pomiń atrybuty style="…"'
    )
    args = parser.parse_args()
    for plik in args.pliki:
        zmieniony = przepisz_plik(plik, inline=not args.bez_inline)
        print(("zmieniony  " if zmieniony else "bez zmian ") + str(plik))


if __name__ == "__main__":
    main()
