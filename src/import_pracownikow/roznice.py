"""Rejestr pól różnic importu pracowników — jedno źródło prawdy dla
``stany_pol()`` (model), paska filtrów oraz atrybutów ``data-diff-*`` w
szablonie.

Każdy wpis: ``(klucz, etykieta, ekstraktor)``. ``ekstraktor(row) ->
"zmienione" | "zgodne" | "brak"``. Trzy stany ROZŁĄCZNE: „brak" = pole puste w
pliku (albo brak dopasowanego autora/AJ dla pól zależnych od autora);
„zmienione" = plik wskazuje wartość różną od bazy; „zgodne" = reszta.
Dodanie kolejnego pola do filtra = jeden wpis tutaj.
"""


def _dane(row):
    return row.dane_znormalizowane or {}


def _stan_jednostka(row):
    if row.jednostka_id is None:
        return "brak"
    # Matched autor + jednostka docelowa różna od obecnej. Obecna=None (autor bez
    # aktualnego zatrudnienia) też liczy się jako „zmienione" — integracja utworzy
    # mu nowe AJ (spec: aktualna_jednostka_id != jednostka_id).
    zmienione = bool(
        row.autor_id and row.autor.aktualna_jednostka_id != row.jednostka_id
    )
    return "zmienione" if zmienione else "zgodne"


def _stan_email(row):
    if not _dane(row).get("email"):
        return "brak"
    return "zmienione" if row.porownaj_z_baza()["email"]["rozne"] else "zgodne"


def _stan_stopien(row):
    if not _dane(row).get("stopień_służbowy"):
        return "brak"
    return "zmienione" if row.porownaj_z_baza()["stopien"]["rozne"] else "zgodne"


def _stan_stanowisko(row):
    if not _dane(row).get("stanowisko_dydaktyczne"):
        return "brak"
    return "zmienione" if row.porownaj_z_baza()["stanowisko"]["rozne"] else "zgodne"


def _stan_tytul(row):
    # niuans: brak dopasowanego autora → neutralne „brak" (komparator też bez
    # podświetlenia, bo porownaj_z_baza daje wtedy rozne=False).
    if row.tytul_id is None or not row.autor_id:
        return "brak"
    return "zmienione" if row.tytul_id != row.autor.tytul_id else "zgodne"


def _stan_funkcja(row):
    if row.funkcja_autora_id is None or row.autor_jednostka is None:
        return "brak"
    return (
        "zmienione"
        if row.autor_jednostka.funkcja_id != row.funkcja_autora_id
        else "zgodne"
    )


def _stan_data_od(row):
    # „brak" gdy plik nie niesie daty od, albo wiersz nie ma autora/jednostki
    # (nie ma okresu do rozstrzygnięcia). Inaczej stan bierzemy z porównywarki:
    # „zmienione" = nowy okres LUB wypełnienie pustej daty od w bazie.
    if row.jednostka_id is None or not row.autor_id:
        return "brak"
    if not _dane(row).get("data_zatrudnienia"):
        return "brak"
    return "zmienione" if row.porownaj_z_baza()["data_od"]["rozne"] else "zgodne"


def _stan_data_do(row):
    # „brak" gdy plik nie niesie daty końca, albo wiersz nie ma autora/jednostki.
    # „zmienione" = wstawienie do pustej, różnica pokazana bez nadpisania, albo
    # nowy okres z niepustą datą końca.
    if row.jednostka_id is None or not row.autor_id:
        return "brak"
    if not _dane(row).get("data_końca_zatrudnienia"):
        return "brak"
    return "zmienione" if row.porownaj_z_baza()["data_do"]["rozne"] else "zgodne"


POLA_ROZNIC = [
    ("jednostka", "Jednostka", _stan_jednostka),
    ("email", "E-mail", _stan_email),
    ("tytul", "Tytuł naukowy", _stan_tytul),
    ("stopien", "Stopień służbowy", _stan_stopien),
    ("funkcja", "Funkcja w jednostce", _stan_funkcja),
    ("stanowisko", "Stanowisko dydaktyczne", _stan_stanowisko),
    ("data_od", "Data od", _stan_data_od),
    ("data_do", "Data do", _stan_data_do),
]
