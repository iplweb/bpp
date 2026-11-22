"""Wykresy SVG zestawień „Metryki jednostki” i „Metryki wydziału” (FD#617).

Generowane po stronie serwera jako inline SVG: WeasyPrint renderuje je
wektorowo do PDF-a, a podgląd HTML pokazuje to samo. Bez zależności od
bibliotek wykresów i bez JavaScriptu.

Kolory: statusy (dobry / średni / słaby) zawsze idą w parze z etykietą
albo ikoną — kolor nigdy nie jest jedynym nośnikiem informacji.
"""

from __future__ import annotations

import math
from decimal import Decimal

from django.utils.html import escape
from django.utils.safestring import mark_safe

from . import metryki_jednostek as r

TLO_PIERSCIENIA = "#e1e0d9"
OS = "#c3c2b7"
SIATKA = "#e1e0d9"
TEKST = "#0b0b0b"
TEKST_DRUGORZEDNY = "#52514e"
NIEBIESKI = "#2a78d6"

KOLOR_STATUSU = {
    r.DOBRY: "#0ca30c",
    r.SREDNI: "#fab219",
    r.SLABY: "#d03b3b",
    r.BRAK: "#9a9890",
}

KOLOR_KWADRANTU = {
    r.KWADRANT_FILAR: "#0ca30c",
    r.KWADRANT_POTENCJAL: NIEBIESKI,
    r.KWADRANT_ILOSC: "#fab219",
    r.KWADRANT_WSPARCIE: "#d03b3b",
    r.KWADRANT_BRAK: "#9a9890",
}

# Struktura punktacji: rampa porządkowa jednego odcienia, od najciemniejszego
# (najwyżej punktowane prace) do najjaśniejszego (nie jaśniej niż krok 250).
KOLORY_PRZEDZIALOW = (
    "#0d366b",
    "#184f95",
    "#256abf",
    "#3987e5",
    "#6da7ec",
    "#86b6ef",
)


def _f(x: float) -> str:
    return f"{x:.1f}"


def _luk(cx, cy, promien, ulamek) -> str:
    """Ścieżka łuku od godziny 12, zgodnie z ruchem wskazówek zegara."""
    kat = 2 * math.pi * ulamek
    x = cx + promien * math.sin(kat)
    y = cy - promien * math.cos(kat)
    duzy = 1 if ulamek > 0.5 else 0
    return (
        f"M {_f(cx)} {_f(cy - promien)} "
        f"A {_f(promien)} {_f(promien)} 0 {duzy} 1 {_f(x)} {_f(y)}"
    )


def pierscien(procent, kolor, tekst, rozmiar=54, grubosc=6):
    """Kółko-wskaźnik: pierścień wypełniony w ``procent`` (0–100+)."""
    ulamek = max(0.0, min(float(procent or 0) / 100, 1.0))
    c = rozmiar / 2
    promien = c - grubosc / 2 - 1
    czesci = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{rozmiar}" '
        f'height="{rozmiar}" viewBox="0 0 {rozmiar} {rozmiar}" '
        f'font-family="Inter, DejaVu Sans, Arial" '
        f'role="img" aria-label="{escape(tekst)}">',
        f'<circle cx="{_f(c)}" cy="{_f(c)}" r="{_f(promien)}" fill="none" '
        f'stroke="{TLO_PIERSCIENIA}" stroke-width="{grubosc}"/>',
    ]
    if ulamek >= 0.999:
        czesci.append(
            f'<circle cx="{_f(c)}" cy="{_f(c)}" r="{_f(promien)}" fill="none" '
            f'stroke="{kolor}" stroke-width="{grubosc}"/>'
        )
    elif ulamek > 0:
        czesci.append(
            f'<path d="{_luk(c, c, promien, ulamek)}" fill="none" '
            f'stroke="{kolor}" stroke-width="{grubosc}" stroke-linecap="round"/>'
        )
    czesci.append(
        f'<text x="{_f(c)}" y="{_f(c + 3.5)}" text-anchor="middle" '
        f'font-size="{10 if len(tekst) <= 4 else 8.5}" font-weight="bold" '
        f'fill="{TEKST}">{escape(tekst)}</text>'
    )
    czesci.append("</svg>")
    return mark_safe("".join(czesci))


def pierscien_wypelnienia(wiersz):
    return pierscien(
        min(wiersz.wypelnienie, Decimal(100)),
        KOLOR_STATUSU[wiersz.status_wypelnienia],
        f"{wiersz.wypelnienie:.0f}%",
    )


def pierscien_punktow(wiersz):
    return pierscien(
        wiersz.udzial_w_maksimum_punktow,
        NIEBIESKI,
        f"{wiersz.punkty:.0f}",
    )


def pierscien_jednostki(procent, tekst, kolor=NIEBIESKI):
    return pierscien(procent, kolor, tekst, rozmiar=86, grubosc=10)


def _skala(wartosc, od, do, piks_od, piks_do):
    if do == od:
        return piks_od
    return piks_od + (wartosc - od) / (do - od) * (piks_do - piks_od)


def _ladny_krok(zakres, liczba=5):
    surowy = zakres / liczba if zakres else 1
    potega = 10 ** math.floor(math.log10(surowy))
    for mnoznik in (1, 2, 2.5, 5, 10):
        if mnoznik * potega >= surowy:
            return mnoznik * potega
    return 10 * potega


def wykres_babelkowy(grupa, szerokosc=760, wysokosc=400, dopelniacz="jednostki"):
    """Oś X: wypełnienie slotów (%), oś Y: średnia punktów za slot,
    pole bąbla: punkty nazbierane. Linie podziału: próg wypełnienia
    i mediana jakości w jednostce (skala „do realiów jednostki”).
    ``dopelniacz`` — „jednostki” / „wydziału” w podpisie mediany."""
    wiersze = [w for w in grupa.wiersze if w.kwadrant != r.KWADRANT_BRAK]
    if not wiersze:
        return ""

    lewy, prawy, gora, dol = 52, 130, 16, 40
    x0, x1 = lewy, szerokosc - prawy
    y0, y1 = wysokosc - dol, gora

    # Zapas 6% za setką, żeby bąble przy pełnych slotach nie były ucięte
    max_x = max(100.0, max(float(w.wypelnienie) for w in wiersze)) * 1.06
    max_y_dane = max(float(w.srednia) for w in wiersze)
    krok_y = _ladny_krok(max_y_dane * 1.1)
    max_y = math.ceil(max_y_dane * 1.1 / krok_y) * krok_y
    max_pkt = max(float(w.punkty) for w in wiersze) or 1.0

    def px(v):
        return _skala(float(v), 0, max_x, x0, x1)

    def py(v):
        return _skala(float(v), 0, max_y, y0, y1)

    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" '
        f'viewBox="0 0 {szerokosc} {wysokosc}" font-family="Inter, DejaVu Sans, Arial" '
        f'role="img" aria-label="Wykres efektywności autorów w dyscyplinie '
        f'{escape(grupa.dyscyplina.nazwa)}">'
    ]

    # Siatka i osie
    v = 0.0
    while v <= max_y + 1e-9:
        y = py(v)
        s.append(
            f'<line x1="{x0}" y1="{_f(y)}" x2="{x1}" y2="{_f(y)}" '
            f'stroke="{SIATKA}" stroke-width="0.6"/>'
            f'<text x="{x0 - 6}" y="{_f(y + 3)}" text-anchor="end" font-size="9" '
            f'fill="{TEKST_DRUGORZEDNY}">{v:g}</text>'
        )
        v += krok_y
    for v in range(0, int(max_x / 1.06) + 1, 20):
        x = px(v)
        s.append(
            f'<text x="{_f(x)}" y="{y0 + 14}" text-anchor="middle" font-size="9" '
            f'fill="{TEKST_DRUGORZEDNY}">{v}%</text>'
        )
    s.append(
        f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="{OS}"/>'
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="{OS}"/>'
        f'<text x="{_f((x0 + x1) / 2)}" y="{wysokosc - 6}" text-anchor="middle" '
        f'font-size="10" fill="{TEKST}">Wypełnienie slotów →</text>'
        f'<text x="12" y="{_f((y0 + y1) / 2)}" text-anchor="middle" '
        f'font-size="10" fill="{TEKST}" '
        f'transform="rotate(-90 12 {_f((y0 + y1) / 2)})">'
        f"Średnia punktów za slot →</text>"
    )

    # Linie podziału na ćwiartki
    xp = px(r.PROG_KWADRANTU_WYPELNIENIE)
    s.append(
        f'<line x1="{_f(xp)}" y1="{y0}" x2="{_f(xp)}" y2="{y1}" stroke="{OS}" '
        f'stroke-dasharray="4 3"/>'
    )
    if grupa.mediana_sredniej is not None:
        ym = py(grupa.mediana_sredniej)
        s.append(
            f'<line x1="{x0}" y1="{_f(ym)}" x2="{x1}" y2="{_f(ym)}" '
            f'stroke="{OS}" stroke-dasharray="4 3"/>'
        )
        # Podpis mediany na prawym marginesie (poza polem wykresu, żeby nie
        # zasłaniał podpisów bąbli), ale poniżej legendy ćwiartek.
        y_podpisu = max(ym + 3, gora + 120)
        s.append(
            f'<text x="{x1 + 4}" y="{_f(y_podpisu)}" font-size="8.5" '
            f'fill="{TEKST_DRUGORZEDNY}">- - mediana</text>'
            f'<text x="{x1 + 4}" y="{_f(y_podpisu + 10)}" font-size="8.5" '
            f'fill="{TEKST_DRUGORZEDNY}">{escape(dopelniacz)}: '
            f"{float(grupa.mediana_sredniej):.1f}</text>"
            f'<text x="{x1 + 4}" y="{_f(y_podpisu + 20)}" font-size="8.5" '
            f'fill="{TEKST_DRUGORZEDNY}">pkt/slot</text>'
        )

    # Bąble: największe pod spodem, żeby małe nie znikały
    for w in sorted(wiersze, key=lambda w: -w.punkty):
        promien = 4 + 16 * math.sqrt(float(w.punkty) / max_pkt)
        cx, cy = px(w.wypelnienie), py(w.srednia)
        kolor = KOLOR_KWADRANTU[w.kwadrant]
        s.append(
            f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(promien)}" '
            f'fill="{kolor}" fill-opacity="0.55" stroke="#ffffff" '
            f'stroke-width="1.5"/>'
        )
    s.extend(_etykiety_babli(wiersze, px, py, max_pkt, x1, y0, y1))

    # Legenda ćwiartek (kolor zawsze z opisem)
    ly = gora + 4
    for kwadrant in (
        r.KWADRANT_FILAR,
        r.KWADRANT_POTENCJAL,
        r.KWADRANT_ILOSC,
        r.KWADRANT_WSPARCIE,
    ):
        s.append(
            f'<circle cx="{x1 + 10}" cy="{ly}" r="5" '
            f'fill="{KOLOR_KWADRANTU[kwadrant]}" fill-opacity="0.55"/>'
        )
        slowa = r.opis_kwadrantu(kwadrant, grupa.slowa).split(", ")
        for i, slowo in enumerate(slowa):
            s.append(
                f'<text x="{x1 + 19}" y="{ly + 3 + i * 10}" font-size="8.5" '
                f'fill="{TEKST}">{escape(slowo)}</text>'
            )
        ly += 14 + 10 * len(slowa)

    s.append("</svg>")
    return mark_safe("".join(s))


WYSOKOSC_PODPISU = 9.0


def _liczba_kolizji(prostokat, zajete, bable, wlasny):
    """Ile podpisów i cudzych bąbli przecina prostokąt (x_od, x_do, g, d)."""
    x_od, x_do, g, d = prostokat
    n = sum(
        1
        for zo, zd, zg, zdl in zajete
        if x_od < zd and zo < x_do and g < zdl and zg < d
    )
    for klucz, (cx, cy, promien) in bable.items():
        if klucz == wlasny:
            continue
        # najbliższy punkt prostokąta do środka bąbla
        nx, ny = min(max(cx, x_od), x_do), min(max(cy, g), d)
        if (nx - cx) ** 2 + (ny - cy) ** 2 < promien * promien:
            n += 1
    return n


def _kandydaci_podpisu(cx, cy, promien, szerokosc, x1, y_dol, y_gora):
    """Pozycje podpisu od najlepszej: na prawo / na lewo od bąbla, z coraz
    większym przesunięciem w pionie (na zmianę w górę i w dół)."""
    prawa = (cx + promien + 2, cx + promien + 2 + szerokosc)
    lewa = (cx - promien - 2 - szerokosc, cx - promien - 2)
    strony = [prawa, lewa] if prawa[1] <= x1 else [lewa]
    for krok in range(9):
        y = cy + 3 + ((krok + 1) // 2) * WYSOKOSC_PODPISU * (1 if krok % 2 else -1)
        if y_gora + WYSOKOSC_PODPISU <= y <= y_dol:
            for x_od, x_do in strony:
                yield (x_od, x_do, y - WYSOKOSC_PODPISU + 2, y + 2), y


def _etykiety_babli(wiersze, px, py, max_pkt, x1, y_dol, y_gora):
    """Podpisy nazwisk przy bąblach, bez nakładania się na inne podpisy
    ani na cudze bąble.

    Osoby o podobnych wynikach lądują w jednym miejscu wykresu (typowo
    skupisko przy 100% wypełnienia). Bierzemy pierwszą pozycję bez kolizji
    (patrz ``_kandydaci_podpisu``), a gdy takiej nie ma — najmniej kolidującą."""
    bable = {
        id(w): (
            px(w.wypelnienie),
            py(w.srednia),
            4 + 16 * math.sqrt(float(w.punkty) / max_pkt),
        )
        for w in wiersze
    }
    # Przy dużych grupach (zestawienie wydziału) podpisujemy tylko osoby
    # z największą liczbą punktów i tylko tam, gdzie podpis mieści się bez
    # kolizji — reszta to bąble bez nazwiska (są w liście efektywności),
    # inaczej podpisy w skupisku przy 100% zlewają się w nieczytelną plamę.
    duza_grupa = len(wiersze) > r.MAX_PODPISOW_WYKRESU
    do_podpisu = sorted(wiersze, key=lambda w: -float(w.punkty))[
        : r.MAX_PODPISOW_WYKRESU
    ]
    zajete = []
    wynik = []
    for w in sorted(
        do_podpisu, key=lambda w: (-float(w.srednia), w.autor.nazwisko or "")
    ):
        cx, cy, promien = bable[id(w)]
        nazwisko = w.autor.nazwisko or ""
        najlepsza = None
        for prostokat, y in _kandydaci_podpisu(
            cx, cy, promien, 4.6 * len(nazwisko) + 2, x1, y_dol, y_gora
        ):
            n = _liczba_kolizji(prostokat, zajete, bable, id(w))
            if najlepsza is None or n < najlepsza[0]:
                najlepsza = (n, prostokat, y)
            if n == 0:
                break
        if duza_grupa and (najlepsza is None or najlepsza[0] > 0):
            continue
        if najlepsza is None:  # brak miejsca w pionie — zostaw przy bąblu
            najlepsza = (0, (cx + promien + 2, cx + promien + 2, cy, cy), cy + 3)
        _, prostokat, y = najlepsza
        zajete.append(prostokat)
        wynik.append(
            f'<text x="{_f(prostokat[0])}" y="{_f(y)}" font-size="8" '
            f'fill="{TEKST}">{escape(nazwisko)}</text>'
        )
    return wynik


def pasek_struktury(grupa, szerokosc=760, wysokosc=26):
    """Pasek 100%: udział slotów wypełnionych pracami z danego przedziału
    punktowego."""
    if grupa.procent_slotow_slabych_prac is None:
        return ""
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" '
        f'viewBox="0 0 {szerokosc} {wysokosc}" role="img" '
        f'aria-label="Struktura punktacji prac">'
    ]
    x = 0.0
    for przedzial, kolor in zip(grupa.struktura, KOLORY_PRZEDZIALOW, strict=True):
        dlugosc = float(przedzial.procent_slotow) / 100 * szerokosc
        if dlugosc <= 0:
            continue
        s.append(
            f'<rect x="{_f(x)}" y="0" width="{_f(max(dlugosc - 2, 0.5))}" '
            f'height="{wysokosc}" rx="3" fill="{kolor}"/>'
        )
        if dlugosc > 34:
            tekst_kolor = "#ffffff" if kolor in KOLORY_PRZEDZIALOW[:4] else TEKST
            s.append(
                f'<text x="{_f(x + dlugosc / 2)}" y="{wysokosc / 2 + 4}" '
                f'text-anchor="middle" font-size="10" font-family="Inter, DejaVu Sans" '
                f'fill="{tekst_kolor}">{float(przedzial.procent_slotow):.0f}%</text>'
            )
        x += dlugosc
    s.append("</svg>")
    return mark_safe("".join(s))
