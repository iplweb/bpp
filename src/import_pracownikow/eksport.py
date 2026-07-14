"""Generator pliku „po imporcie" — kanoniczny, SKORYGOWANY XLSX.

Odbija stan BAZY po imporcie: wartości czytane z autorytatywnych rekordów
(``Autor`` / ``Autor_Jednostka``), nie z pliku ani z proponowanych FK wiersza.
Kanoniczne nagłówki (auto-rozpoznawane) + kolumna ``BPP ID`` → plik re-importuje
się bezobsługowo.
"""

from io import BytesIO

from django.core.files.base import ContentFile
from openpyxl import Workbook
from openpyxl.styles import Font

from bpp.util.xlsx import sanitize_xlsx_row
from import_pracownikow.mapping import POLE_POMIN


def _tekst(v):
    return "" if v is None else str(v)


def _iso(d):
    return "" if d is None else d.isoformat()


def _tak_nie(v):
    return "" if v is None else ("T" if v else "N")


def _jednostka(row):
    aj = row.autor_jednostka
    return aj.jednostka.nazwa if aj and aj.jednostka_id else ""


def _pbn(row):
    # AutorForm.pbn_uuid wymaga DOKŁADNIE 24 znaków; nietypowa wartość
    # wywaliłaby re-import (fail-fast). Emitujemy tylko poprawne 24-znakowe.
    v = row.autor.pbn_uid_id
    return v if v is not None and len(str(v)) == 24 else ""


# (nagłówek, targety_włączające, getter(row), tryb)
# tryb: "always" | "attr" | "id_enrich"
REJESTR = [
    ("BPP ID", (), lambda r: r.autor_id, "always"),
    (
        "Nazwisko",
        ("nazwisko", "osoba_sklejona", "nazwisko_imię"),
        lambda r: _tekst(r.autor.nazwisko),
        "always",
    ),
    (
        "Imię",
        ("imię", "osoba_sklejona", "nazwisko_imię"),
        lambda r: _tekst(r.autor.imiona),
        "always",
    ),
    ("ORCID", ("orcid",), lambda r: _tekst(r.autor.orcid), "id_enrich"),
    ("PBN UUID", ("pbn_uuid",), _pbn, "id_enrich"),
    ("Numer", ("numer",), lambda r: _tekst(r.autor.system_kadrowy_id), "id_enrich"),
    ("E-mail", ("email",), lambda r: _tekst(r.autor.email), "attr"),
    (
        "Nazwa jednostki",
        ("nazwa_jednostki", "nazwa_jednostki_niepelna", "komórka_złożona", "wydział"),
        _jednostka,
        "always",
    ),
    ("Tytuł", ("tytuł_stopień",), lambda r: _tekst(r.autor.tytul), "attr"),
    (
        "Stopień służbowy",
        ("stopień_służbowy",),
        lambda r: _tekst(r.autor.stopien_sluzbowy),
        "attr",
    ),
    (
        "Funkcja w jednostce",
        ("stanowisko",),
        lambda r: _tekst(r.autor_jednostka.funkcja) if r.autor_jednostka else "",
        "attr",
    ),
    (
        "Stanowisko dydaktyczne",
        ("stanowisko_dydaktyczne",),
        lambda r: _tekst(r.autor_jednostka.stanowisko) if r.autor_jednostka else "",
        "attr",
    ),
    (
        "Grupa pracownicza",
        ("grupa_pracownicza",),
        lambda r: (
            _tekst(r.autor_jednostka.grupa_pracownicza) if r.autor_jednostka else ""
        ),
        "attr",
    ),
    (
        "Wymiar etatu",
        ("wymiar_etatu_tekst", "wymiar_etatu_ulamek"),
        lambda r: _tekst(r.autor_jednostka.wymiar_etatu) if r.autor_jednostka else "",
        "attr",
    ),
    (
        "Data zatrudnienia",
        ("data_zatrudnienia",),
        lambda r: _iso(r.autor_jednostka.rozpoczal_prace) if r.autor_jednostka else "",
        "attr",
    ),
    (
        "Data końca zatrudnienia",
        ("data_końca_zatrudnienia",),
        lambda r: _iso(r.autor_jednostka.zakonczyl_prace) if r.autor_jednostka else "",
        "attr",
    ),
    (
        "Podstawowe miejsce pracy",
        ("podstawowe_miejsce_pracy",),
        lambda r: (
            _tak_nie(r.autor_jednostka.podstawowe_miejsce_pracy)
            if r.autor_jednostka
            else ""
        ),
        "attr",
    ),
]


def _wiersze_do_eksportu(import_obj):
    qs = import_obj.get_details_set().select_related(
        "autor",
        "autor__tytul",
        "autor__stopien_sluzbowy",
        "autor_jednostka",
        "autor_jednostka__jednostka",
        "autor_jednostka__funkcja",
        "autor_jednostka__stanowisko",
        "autor_jednostka__grupa_pracownicza",
        "autor_jednostka__wymiar_etatu",
    )
    return [r for r in qs if r.autor_id is not None]


def _kolumny_do_emisji(import_obj, wiersze):
    uzyte = set((import_obj.mapowanie_kolumn or {}).values()) - {POLE_POMIN}
    kolumny = []
    for naglowek, targety, getter, tryb in REJESTR:
        if tryb == "always":
            emit = True
        elif tryb == "attr":
            emit = bool(set(targety) & uzyte)
        elif tryb == "id_enrich":
            emit = bool(set(targety) & uzyte) or any(getter(r) for r in wiersze)
        else:
            raise ValueError(f"Nieznany tryb kolumny: {tryb}")
        if emit:
            kolumny.append((naglowek, getter))
    return kolumny


def zbuduj_plik_po_imporcie(import_obj) -> bytes:
    wiersze = _wiersze_do_eksportu(import_obj)
    kolumny = _kolumny_do_emisji(import_obj, wiersze)

    wb = Workbook()
    ws = wb.active
    ws.title = "po imporcie"
    ws.append([naglowek for naglowek, _ in kolumny])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"
    for r in wiersze:
        ws.append(sanitize_xlsx_row([getter(r) for _, getter in kolumny]))

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def zapisz_snapshot_po_imporcie(import_obj):
    """Buduje i ZAPISUJE zamrożony plik „po imporcie" do pola
    ``plik_po_imporcie`` (trwały rekord przy finalizacji). Nazwa w storage
    bazuje na pk; nazwę POBIERANIA ustala widok."""
    tresc = zbuduj_plik_po_imporcie(import_obj)
    import_obj.plik_po_imporcie.save(
        f"po-imporcie-{import_obj.pk}.xlsx", ContentFile(tresc), save=True
    )
