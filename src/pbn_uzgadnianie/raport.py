"""Raport przebiegu do pobrania (XLSX) i grupowanie wpisów dla strony."""

import io
import re
from difflib import SequenceMatcher

from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from openpyxl import Workbook
from openpyxl.styles import Font

from bpp.util import sanitize_xlsx_row, worksheet_columns_autosize

from .silnik import KATEGORIE
from .swiezosc import linie_opisu, stan_danych

NAGLOWKI = [
    "Co się stało",
    "PBN UID",
    "Tytuł w PBN",
    "Rok w PBN",
    "Typ w PBN",
    "DOI w PBN",
    "Rekord BPP (rodzaj)",
    "Rekord BPP (ID)",
    "Tytuł w BPP",
    "Rok w BPP",
    "Użyta wersja z PBN",
    "Sposób dopasowania",
    "Różnice (pole: BPP → PBN)",
    "Dyscypliny w nowym rekordzie",
    "Powód / uwagi",
    "Drugi rekord BPP (ID)",
    "Drugi rekord BPP (tytuł)",
]

NAGLOWKI_ROZNIC = [
    "PBN UID (ten sam po obu stronach)",
    "Rekord BPP (rodzaj)",
    "Rekord BPP (ID)",
    "Tytuł w BPP",
    "Pole",
    "Wartość w BPP",
    "Wartość w PBN",
]


BRAK = "(brak)"

_SLOWA = re.compile(r"\s+|[^\s]+")


def wartosc_roznicy(roznica, strona):
    """Wartość po stronie ``"bpp"`` / ``"pbn"``; pustą opisujemy słowami."""
    return roznica.get(strona) or roznica.get(f"brak_{strona}") or BRAK


def _podswietl(tekst, inny):
    """``tekst`` jako HTML, z ``<mark>`` na fragmentach różnych od ``inny``.

    Porównanie słowo po słowie — w długim tytule widać od razu, które
    słowa się różnią, zamiast dwóch akapitów do porównywania wzrokiem.
    """
    a, b = _SLOWA.findall(tekst), _SLOWA.findall(inny)
    czesci = []
    for operacja, a0, a1, _b0, _b1 in SequenceMatcher(
        None, a, b, autojunk=False
    ).get_opcodes():
        fragment = escape("".join(a[a0:a1]))
        if not fragment:
            continue
        if operacja == "equal" or not fragment.strip():
            czesci.append(fragment)
        else:
            czesci.append(f"<mark>{fragment}</mark>")
    return mark_safe("".join(czesci))  # noqa: S308 — każdy fragment po escape()


def wiersze_roznic(wpis):
    """Różnice wpisu — po jednej na wiersz: pole, wartość w BPP, w PBN.

    ``*_html`` ma wyróżnione fragmenty, które się różnią; pusta strona to
    cała wartość wyróżniona słowem (np. „brak oświadczenia w PBN”).
    """
    wiersze = []
    for roznica in wpis.get("roznice", []):
        bpp, pbn = roznica.get("bpp") or "", roznica.get("pbn") or ""
        wiersze.append(
            {
                "pole": roznica["pole"],
                "bpp": wartosc_roznicy(roznica, "bpp"),
                "pbn": wartosc_roznicy(roznica, "pbn"),
                "bpp_html": _podswietl(bpp, pbn)
                if bpp
                else format_html("<em>{}</em>", wartosc_roznicy(roznica, "bpp")),
                "pbn_html": _podswietl(pbn, bpp)
                if pbn
                else format_html("<em>{}</em>", wartosc_roznicy(roznica, "pbn")),
            }
        )
    return wiersze


def opis_roznic(wpis):
    """Różnice w jednej linii (skrót do arkusza „Raport”)."""
    return "; ".join(
        f"{w['pole']}: „{w['bpp']}” → „{w['pbn']}”" for w in wiersze_roznic(wpis)
    )


def opis_dyscyplin(wpis):
    """Dyscypliny nowego rekordu: co przypisano, czego nie i dlaczego."""
    return "; ".join(
        f"{d['osoba']}: {d['dyscyplina']}"
        if d["przypisano"]
        else f"{d['osoba']}: BEZ DYSCYPLINY — {d['powod']}"
        for d in wpis.get("dyscypliny", [])
    )


def wiersz(wpis):
    return [
        KATEGORIE[wpis["kategoria"]],
        wpis.get("pbn_uid", ""),
        wpis.get("pbn_tytul", ""),
        wpis.get("pbn_rok", ""),
        wpis.get("pbn_typ", ""),
        wpis.get("pbn_doi", ""),
        wpis.get("bpp_model", ""),
        wpis.get("bpp_pk", ""),
        wpis.get("bpp_tytul", ""),
        wpis.get("bpp_rok", ""),
        wpis.get("wersja", ""),
        wpis.get("dopasowanie", ""),
        opis_roznic(wpis),
        opis_dyscyplin(wpis),
        " ".join(
            x
            for x in (
                wpis.get("powod"),
                wpis.get("uwaga"),
                f"Wysyłka z BPP: {wpis['wysylka']}." if wpis.get("wysylka") else "",
            )
            if x
        ),
        (wpis.get("blizniak") or {}).get("bpp_pk", ""),
        (wpis.get("blizniak") or {}).get("bpp_tytul", ""),
    ]


def pogrupuj(wpisy):
    """``[(kod, etykieta, [wpisy])]`` w kolejności ``KATEGORIE``, bez pustych."""
    grupy = {kod: [] for kod in KATEGORIE}
    for wpis in wpisy:
        grupy[wpis["kategoria"]].append(wpis)
    return [(kod, KATEGORIE[kod], grupy[kod]) for kod in KATEGORIE if grupy[kod]]


def zbuduj_xlsx(uzgodnienie):
    """Zwraca bajty skoroszytu: arkusz „Podsumowanie” + arkusz „Raport”."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Podsumowanie"
    for linia in (
        ["Uzgodnienie z PBN", str(uzgodnienie.uczelnia)],
        ["Lata", f"{uzgodnienie.rok_od}–{uzgodnienie.rok_do}"],
        ["Tryb", uzgodnienie.get_tryb_display()],
        ["Status", uzgodnienie.get_status_display()],
        ["Uruchomiono", str(uzgodnienie.rozpoczeto or uzgodnienie.utworzono)],
        ["Uruchomił(a)", str(uzgodnienie.user or "")],
        *[[linia] for linia in linie_opisu(stan_danych(uzgodnienie.zakres))],
        [],
    ):
        ws.append(sanitize_xlsx_row(linia))
    for kod, etykieta in KATEGORIE.items():
        ws.append([etykieta, (uzgodnienie.podsumowanie or {}).get(kod, 0)])
    worksheet_columns_autosize(ws)

    ws = wb.create_sheet("Raport")
    ws.append(NAGLOWKI)
    for komorka in ws[1]:
        komorka.font = Font(bold=True)
    for _kod, _etykieta, wpisy in pogrupuj(uzgodnienie.wynik or []):
        for wpis in wpisy:
            ws.append(sanitize_xlsx_row(wiersz(wpis)))
    ws.freeze_panes = "A2"
    worksheet_columns_autosize(ws)

    # Każda różnica w osobnym wierszu: pole | BPP | PBN.
    ws = wb.create_sheet("Różnice")
    ws.append(NAGLOWKI_ROZNIC)
    for komorka in ws[1]:
        komorka.font = Font(bold=True)
    for wpis in uzgodnienie.wynik or []:
        for roznica in wiersze_roznic(wpis):
            ws.append(
                sanitize_xlsx_row(
                    [
                        wpis.get("pbn_uid", ""),
                        wpis.get("bpp_model", ""),
                        wpis.get("bpp_pk", ""),
                        wpis.get("bpp_tytul", ""),
                        roznica["pole"],
                        roznica["bpp"],
                        roznica["pbn"],
                    ]
                )
            )
    ws.freeze_panes = "A2"
    worksheet_columns_autosize(ws)

    bufor = io.BytesIO()
    wb.save(bufor)
    return bufor.getvalue()
