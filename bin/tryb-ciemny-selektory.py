#!/usr/bin/env python
"""Pomocnik do trybu ciemnego: wypisuje selektory z jasnym tłem i ciemnym
tekstem ze skompilowanego (rozwiniętego) CSS motywu, pogrupowane według
koloru zastępczego z palety `_tryb-ciemny.scss`.

To NIE jest krok builda. Służy do (od)świeżenia listy w
``src/bpp/static/scss/_tryb-ciemny-komponenty.scss`` po dodaniu nowych
komponentów — wynik trzeba przejrzeć ręcznie (przyciski z kolorowym tłem,
elementy celowo jasne itp.) i dopiero wtedy wkleić.

Użycie::

    npx sass --no-source-map -q \\
        --silence-deprecation=import,global-builtin,if-function \\
        --load-path=node_modules/foundation-sites/scss \\
        src/bpp/static/scss/app-blue.scss /tmp/app-blue.css
    uv run python bin/tryb-ciemny-selektory.py --szablony /tmp/app-blue.css \\
        > /tmp/wynik.scss

``--szablony`` dokłada reguły z bloków ``<style>`` w szablonach
(``src/**/templates/**/*.html`` bez ``/admin/``). Reguły motywu mają
prefiks ``html``, więc wygrywają z nimi specyficznością mimo późniejszej
pozycji w dokumencie. Wynik zastępuje mixin w
``_tryb-ciemny-komponenty.scss`` (nagłówek pliku zostaw).
"""

import argparse
import colorsys
import re
from collections import defaultdict
from pathlib import Path

import tinycss2
import tinycss2.color4

# Selektory pomijane: obsłużone ogólnie w _tryb-ciemny.scss (Foundation,
# formularze) albo celowo jasne / niewidoczne na ekranie.
POMIJANE_PREFIKSY = (
    "html",
    "body",
    ".button",
    ".badge",
    ".label",
    ".callout",
    ".card",
    ".reveal",
    ".tabs",
    ".accordion",
    ".pagination",
    ".dropdown-pane",
    ".is-dropdown-submenu",
    "thead",
    "tbody",
    "tfoot",
    "table.hover",
    "table.unstriped",
    "[type=",
    "select",
    "textarea",
    "input",
    ".input-group-label",
    ".is-invalid",
    ".top-bar,",
    ".menu-icon",
    "kbd",
    "code",
    ".code-",
    ".progress",
    ".gradient-background",
    ".form-error",
    "a,",
    "a:",
    "label",
    ".help-text",
    ".close-button",
    # Selektory ogólne z bloków <style> w szablonach — tam działają tylko
    # na jednej stronie, w motywie objęłyby całą witrynę.
    "a",
    "th",
    "h1",
    "small",
    "button",
    # Celowo „papierowe” (podgląd wydruku / PDF).
    ".metryki-podglad__kartka",
    ".pdf-footer",
    # Przeniesione do SCSS (uczelnia.scss), obsłużone ręcznie.
    ".browse-tile",
)


# Jasne, neutralne obramowania -> --tc-ramka (właściwość wynikowa).
OBRAMOWANIA = {
    "border": "border-color",
    "border-color": "border-color",
    "border-top": "border-top-color",
    "border-top-color": "border-top-color",
    "border-bottom": "border-bottom-color",
    "border-bottom-color": "border-bottom-color",
    "border-left": "border-left-color",
    "border-left-color": "border-left-color",
    "border-right": "border-right-color",
    "border-right-color": "border-right-color",
    "outline": "outline-color",
}


def style_z_szablonow():
    """Zawartość bloków <style> z szablonów (bez admina), bez tagów Django."""
    korzen = Path(__file__).resolve().parent.parent / "src"
    czesci = []
    for plik in sorted(korzen.glob("**/templates/**/*.html")):
        if "/admin/" in str(plik):
            continue
        tekst = plik.read_text(errors="replace")
        # Samodzielne dokumenty (konfigurator wyglądu, wydruki/PDF) nie
        # ładują motywu — ich ogólne selektory (`button`, `.sekcja`) objęłyby
        # w motywie całą witrynę.
        if "<!DOCTYPE" in tekst.upper() and "{% extends" not in tekst:
            continue
        for m in re.finditer(r"<style[^>]*>(.*?)</style>", tekst, re.S):
            czesci.append(re.sub(r"\{%.*?%\}|\{\{.*?\}\}|\{#.*?#\}", "", m.group(1)))
    return "\n".join(czesci)


def pomijany(selektor):
    """Czy selektor zaczyna się od pomijanego prefiksu (na granicy nazwy:
    `.pagination` pomija `.pagination li`, ale nie `.pagination-btn`)."""
    for p in POMIJANE_PREFIKSY:
        if selektor == p:
            return True
        if selektor.startswith(p):
            if p[-1] in ",=:" or selektor[len(p)] in " .:[>#":
                return True
    return False


def luminancja(r, g, b):
    def f(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def kolory(wartosc_tokeny):
    wynik = []
    for t in wartosc_tokeny:
        if t.type == "function" and "gradient" in t.lower_name:
            wynik.extend(kolory(t.arguments))
            continue
        try:
            c = tinycss2.color4.parse_color(t)
        except (ValueError, TypeError):
            c = None
        if c is None or isinstance(c, str):
            continue
        r, g, b = c.to("srgb").coordinates
        a = c.alpha
        if a is None or a < 0.5:
            continue
        wynik.append((r, g, b))
    return wynik


def odcien(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360, s


def kubel_tla(rgb, selektor):
    r, g, b = rgb
    h, s = odcien(r, g, b)
    hover = ":hover" in selektor or ":focus" in selektor
    if s < 0.08:
        if hover:
            return "--tc-pow-hover"
        if luminancja(r, g, b) >= 0.975:
            return "--tc-pow"
        return "--tc-pow-2"
    if h < 20 or h >= 330:
        return "--tc-blad-tlo"
    if h < 65:
        return "--tc-ostrzezenie-tlo"
    if h < 170:
        return "--tc-sukces-tlo"
    if h < 255:
        return "--tc-info-tlo"
    return "--tc-fiolet-tlo"


def kubel_tekstu(rgb):
    r, g, b = rgb
    h, s = odcien(r, g, b)
    lum = luminancja(r, g, b)
    # Granatowo-szare nagłówki (#2c3e50, #34495e) to tekst, nie akcent.
    if s < 0.6:
        return "--tc-tekst" if lum < 0.08 else "--tc-przygaszony"
    if h < 20 or h >= 330:
        return "--tc-blad-tekst"
    if h < 65:
        return "--tc-ostrzezenie-tekst"
    if h < 170:
        return "--tc-sukces-tekst"
    if h < 255:
        return "--tc-akcent"
    return "--tc-fiolet-tekst"


def reguly(tokeny, w_print=False):
    for r in tokeny:
        if r.type == "at-rule" and r.content is not None:
            prelude = tinycss2.serialize(r.prelude).lower()
            if r.lower_at_keyword == "media":
                pr = "print" in prelude and "screen" not in prelude
                yield from reguly(
                    tinycss2.parse_rule_list(r.content, True, True), w_print or pr
                )
            continue
        if r.type != "qualified-rule" or w_print:
            continue
        sel = tinycss2.serialize(r.prelude).strip()
        dekl = tinycss2.parse_declaration_list(r.content, True, True)
        yield sel, [d for d in dekl if d.type == "declaration"]


def jasna_ramka(kolory_ramki):
    """Jasne, neutralne obramowanie (np. #dee2e6) — razi na ciemnym tle."""
    if not kolory_ramki:
        return False
    c = kolory_ramki[0]
    return luminancja(*c) > 0.55 and odcien(*c)[1] < 0.15


def barwne_tlo_danych(dekl):
    """Gradient z wyraźnie barwnym kolorem (skala „temperatury”) albo
    plakietka (barwne jasne tło + ciemny tekst) — reguła zostaje bez zmian."""
    tlo_barwne = tekst_ciemny = False
    for d in dekl:
        k = kolory(d.value)
        if d.lower_name in ("background", "background-color", "background-image"):
            barwne = [c for c in k if odcien(*c)[1] > 0.25]
            gradient = "gradient" in tinycss2.serialize(d.value)
            if barwne and gradient:
                return True
            if barwne and any(luminancja(*c) > 0.7 for c in barwne):
                tlo_barwne = True
        if d.lower_name == "color" and k and luminancja(*k[0]) < 0.3:
            tekst_ciemny = True
    return tlo_barwne and tekst_ciemny


def klasyfikuj_regule(czesci, dekl, grupy):
    """Dopisz selektory jednej reguły do grup (tło / tekst / ramka)."""
    ma_ciemne_tlo = False
    jasne_tlo = None
    gradient = False
    wazne = False
    tekst = None
    for d in dekl:
        k = kolory(d.value)
        if d.lower_name in ("background", "background-color", "background-image"):
            if any(luminancja(*c) > 0.7 for c in k):
                jasne_tlo = max(k, key=lambda c: luminancja(*c))
                gradient = "gradient" in tinycss2.serialize(d.value)
                wazne = d.important
            elif k:
                ma_ciemne_tlo = True
        if d.lower_name in OBRAMOWANIA and jasna_ramka(k):
            klucz = ("ramka", OBRAMOWANIA[d.lower_name], False, d.important)
            grupy[klucz].extend(czesci)
        if d.lower_name == "color" and k and luminancja(*k[0]) < 0.3:
            tekst = (k[0], d.important)
    for s in czesci:
        if jasne_tlo:
            grupy[("tlo", kubel_tla(jasne_tlo, s), gradient, wazne)].append(s)
        if tekst and not ma_ciemne_tlo:
            grupy[("tekst", kubel_tekstu(tekst[0]), False, tekst[1])].append(s)


def wypisz_mixin(grupy):
    print("@mixin bpp-tryb-ciemny-komponenty {")
    print("  html {")
    for (rodzaj, zmienna, gradient, wazne), selektory in sorted(grupy.items()):
        sel = sorted(dict.fromkeys(selektory))
        imp = " !important" if wazne else ""
        print(f"    // {rodzaj}: {zmienna}{' (gradient)' if gradient else ''}{imp}")
        print("    " + ",\n    ".join(sel) + " {")
        if rodzaj == "tlo":
            if gradient:
                print(f"      background-image: none{imp};")
            print(f"      background-color: var({zmienna}){imp};")
        elif rodzaj == "ramka":
            print(f"      {zmienna}: var(--tc-ramka){imp};")
        else:
            print(f"      color: var({zmienna}){imp};")
        print("    }\n")
    print("  }")
    print("}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("css", nargs="+", help="rozwinięty CSS motywu")
    parser.add_argument(
        "--szablony", action="store_true", help="dołóż bloki <style> z szablonów"
    )
    args = parser.parse_args()

    arkusz = []
    for plik in args.css:
        arkusz.extend(tinycss2.parse_stylesheet(Path(plik).read_text(), True, True))
    if args.szablony:
        arkusz.extend(tinycss2.parse_stylesheet(style_z_szablonow(), True, True))
    grupy = defaultdict(list)
    for sel, dekl in reguly(arkusz):
        czesci = [" ".join(s.split()) for s in sel.split(",")]
        czesci = [s for s in czesci if s and not pomijany(s)]
        if czesci and not barwne_tlo_danych(dekl):
            klasyfikuj_regule(czesci, dekl, grupy)
    wypisz_mixin(grupy)


if __name__ == "__main__":
    main()
