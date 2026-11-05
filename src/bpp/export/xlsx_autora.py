"""Eksport publikacji autora do XLSX z punktacją (§3.3, obok BibTeX/RIS).

Skoroszyt ma dwa arkusze:

- „Publikacje” — wiersz na pracę: rok, tytuł, autorzy, źródło, charakter,
  typ MNiSW/MEiN, IF, PK, dyscyplina autora w pracy oraz (opcjonalnie)
  punktacja autora z cache slotów: PKdAut i slot,
- „Podsumowanie” — sumy w latach (liczba prac, Σ PK, Σ IF, opcjonalnie
  Σ PKdAut i Σ slotów).

Budowane w zadaniu Celery (bez requestu) — zakres widoczności (ukryte
statusy, czy wolno pokazać sloty) przychodzi z ``AutorEksportTask``.
"""

import io
from collections import defaultdict
from decimal import Decimal

NAGLOWKI_PUBLIKACJE = (
    "Rok",
    "Tytuł oryginalny",
    "Autorzy",
    "Źródło",
    "Charakter formalny",
    "Typ MNiSW/MEiN",
    "Impact Factor",
    "PK",
    "Dyscyplina autora",
)
NAGLOWKI_PUNKTACJA_AUTORA = ("PKdAut", "Slot")

NAGLOWKI_PODSUMOWANIE = ("Rok", "Liczba prac", "Σ PK", "Σ IF")
NAGLOWKI_PODSUMOWANIE_AUTORA = ("Σ PKdAut", "Σ slotów")

_POLA_REKORDU = (
    "id",
    "rok",
    "tytul_oryginalny",
    "opis_bibliograficzny_zapisani_autorzy_cache",
    "zrodlo__nazwa",
    "charakter_formalny__nazwa",
    "typ_kbn__nazwa",
    "impact_factor",
    "punkty_kbn",
)


def _klucz(rekord_id):
    """``rekord_id`` (TupleField / lista) → hashowalna krotka."""
    return tuple(rekord_id)


def _dyscypliny_autora(autor):
    from bpp.models import Autorzy

    wynik = defaultdict(set)
    pary = (
        Autorzy.objects.filter(autor=autor)
        .exclude(dyscyplina_naukowa=None)
        .values_list("rekord_id", "dyscyplina_naukowa__nazwa")
    )
    for rekord_id, nazwa in pary:
        wynik[_klucz(rekord_id)].add(nazwa)
    return wynik


def _punktacja_autora(autor, ukryte_statusy_slotow):
    """{rekord: (pkdaut, slot)} z cache punktacji autora."""
    from bpp.models.cache.punktacja import Cache_Punktacja_Autora_Query

    qs = Cache_Punktacja_Autora_Query.objects.filter(autor=autor)
    if ukryte_statusy_slotow:
        qs = qs.exclude(rekord__status_korekty_id__in=list(ukryte_statusy_slotow))
    wynik = {}
    for rekord_id, pkdaut, slot in qs.values_list("rekord_id", "pkdaut", "slot"):
        pk, sl = wynik.get(_klucz(rekord_id), (Decimal(0), Decimal(0)))
        wynik[_klucz(rekord_id)] = (pk + (pkdaut or 0), sl + (slot or 0))
    return wynik


def _ostyluj_naglowek(worksheet):
    from openpyxl.styles import Alignment, Font, PatternFill

    fill = PatternFill("solid", fgColor="1F4E78")
    font = Font(color="FFFFFF", bold=True)
    for cell in worksheet[1]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center", vertical="center")


def _format_kolumn(worksheet, naglowki, formaty):
    for idx, naglowek in enumerate(naglowki, start=1):
        fmt = formaty.get(naglowek)
        if fmt is None:
            continue
        for (cell,) in worksheet.iter_rows(min_row=2, min_col=idx, max_col=idx):
            cell.number_format = fmt


_FORMATY = {
    "Impact Factor": "0.000",
    "PK": "0.00",
    "PKdAut": "0.0000",
    "Slot": "0.0000",
    "Σ PK": "0.00",
    "Σ IF": "0.000",
    "Σ PKdAut": "0.0000",
    "Σ slotów": "0.0000",
}


def _domknij_arkusz(worksheet, naglowki, tytul_tabeli):
    from bpp.util import worksheet_columns_autosize, worksheet_create_table

    _ostyluj_naglowek(worksheet)
    _format_kolumn(worksheet, naglowki, _FORMATY)
    worksheet.freeze_panes = "A2"
    worksheet_columns_autosize(worksheet)
    if worksheet.max_row > 1:
        worksheet_create_table(worksheet, title=tytul_tabeli)


def zbuduj_xlsx_autora(
    autor,
    ukryte_statusy=(),
    z_punktacja_autora=False,
    ukryte_statusy_slotow=(),
    limit=None,
) -> bytes:
    """Zbuduj plik XLSX z publikacjami autora; zwraca bajty skoroszytu.

    ``z_punktacja_autora`` — czy dołożyć kolumny PKdAut/slot (bramka jak
    sekcja „Punkty i sloty w latach” na stronie autora, ustalana przy
    starcie zadania). ``limit`` — maks. liczba prac (zabezpieczenie OOM).
    """
    from openpyxl import Workbook

    from bpp.models import Rekord
    from bpp.util import sanitize_xlsx_row

    qs = Rekord.objects.prace_autora(autor)
    if ukryte_statusy:
        qs = qs.exclude(status_korekty_id__in=list(ukryte_statusy))
    qs = qs.order_by("-rok", "tytul_oryginalny").values_list(*_POLA_REKORDU)
    if limit is not None:
        qs = qs[:limit]

    dyscypliny = _dyscypliny_autora(autor)
    punktacja = (
        _punktacja_autora(autor, ukryte_statusy_slotow) if z_punktacja_autora else {}
    )

    naglowki = NAGLOWKI_PUBLIKACJE
    naglowki_sum = NAGLOWKI_PODSUMOWANIE
    if z_punktacja_autora:
        naglowki = naglowki + NAGLOWKI_PUNKTACJA_AUTORA
        naglowki_sum = naglowki_sum + NAGLOWKI_PODSUMOWANIE_AUTORA

    workbook = Workbook()
    arkusz = workbook.active
    arkusz.title = "Publikacje"
    arkusz.append(naglowki)

    # rok → [liczba, Σ PK, Σ IF, Σ PKdAut, Σ slot]
    sumy = defaultdict(lambda: [0, Decimal(0), Decimal(0), Decimal(0), Decimal(0)])

    for (
        rekord_id,
        rok,
        tytul,
        autorzy,
        zrodlo,
        charakter,
        typ_kbn,
        impact_factor,
        punkty_kbn,
    ) in qs:
        klucz = _klucz(rekord_id)
        wiersz = [
            rok,
            tytul,
            autorzy,
            zrodlo or "",
            charakter or "",
            typ_kbn or "",
            impact_factor,
            punkty_kbn,
            ", ".join(sorted(dyscypliny.get(klucz, ()))),
        ]
        s = sumy[rok]
        s[0] += 1
        s[1] += punkty_kbn or 0
        s[2] += impact_factor or 0
        if z_punktacja_autora:
            pkdaut, slot = punktacja.get(klucz, (None, None))
            wiersz += [pkdaut, slot]
            s[3] += pkdaut or 0
            s[4] += slot or 0
        arkusz.append(sanitize_xlsx_row(wiersz))

    _domknij_arkusz(arkusz, naglowki, "Publikacje")

    podsumowanie = workbook.create_sheet("Podsumowanie")
    podsumowanie.append(naglowki_sum)
    for rok in sorted((r for r in sumy if r is not None), reverse=True):
        liczba, pk, if_, pkdaut, slot = sumy[rok]
        wiersz = [rok, liczba, pk, if_]
        if z_punktacja_autora:
            wiersz += [pkdaut, slot]
        podsumowanie.append(wiersz)
    _domknij_arkusz(podsumowanie, naglowki_sum, "Podsumowanie")

    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()
