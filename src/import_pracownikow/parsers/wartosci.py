"""Normalizacja wartości komórek nad warstwą źródła (CSV + XLSX).

CSV daje wartości jako stringi tam, gdzie XLSX (openpyxl) daje typy natywne
(``datetime`` dla dat). ``ExcelDateField`` obsługuje ``datetime`` i ISO
``YYYY-MM-DD``, ale nie polskie ``DD.MM.YYYY`` — tę lukę zamyka
``normalize_date_pl``. Warstwa jest specyficzna dla importu pracowników
(zna nazwy kolumn-dat), więc siedzi w ``import_pracownikow.parsers``, nie w
generycznym ``import_common``.
"""

from datetime import date, datetime

# Kolumny-daty w rygorystycznym schemacie Fazy 0/1 (nazwy = znormalizowane
# nagłówki wzorca BPP). Faza 2 (mapowanie) uczyni to konfigurowalnym.
_KLUCZE_DAT = ("data_zatrudnienia", "data_końca_zatrudnienia")


def normalize_date_pl(value):
    """datetime/date → ``date``; string ``DD.MM.YYYY`` → ``date``; wszystko
    inne (ISO, puste, nie-data) zwrócone bez zmian — walidację/odrzucenie
    zostawiamy ``ExcelDateField``. Kropka jednoznacznie sygnalizuje zapis
    europejski, więc nie kolidujemy z ``%m/%d/%Y`` z Django defaults."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s:
            try:
                return datetime.strptime(s, "%d.%m.%Y").date()
            except ValueError:
                # nie DD.MM.YYYY (może ISO, może śmieć) — zostaw formularzowi
                return value
    return value


def normalizuj_wartosci_wiersza(elem: dict) -> dict:
    """Zwraca KOPIĘ ``elem`` ze znormalizowanymi kolumnami-datami. Nie mutuje
    wejścia (audyt ``dane_z_xls`` musi zachować surowe wartości)."""
    out = dict(elem)
    for klucz in _KLUCZE_DAT:
        if out.get(klucz) is not None:
            out[klucz] = normalize_date_pl(out[klucz])
    return out
