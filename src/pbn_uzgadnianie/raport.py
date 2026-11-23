"""Raport przebiegu do pobrania (XLSX) i grupowanie wpisów dla strony."""

import io

from openpyxl import Workbook
from openpyxl.styles import Font

from bpp.util import sanitize_xlsx_row, worksheet_columns_autosize

from .silnik import KATEGORIE

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
    "Powód / uwagi",
]


def opis_roznic(wpis):
    return "; ".join(
        f"{r['pole']}: „{r['bpp']}” → „{r['pbn']}”" for r in wpis.get("roznice", [])
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
        " ".join(x for x in (wpis.get("powod"), wpis.get("uwaga")) if x),
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

    bufor = io.BytesIO()
    wb.save(bufor)
    return bufor.getvalue()
