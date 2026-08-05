"""Mapowanie trybu dostępu BPP na COAR Access Rights."""

BAZA = "http://purl.org/coar/access_right/"

OPEN = BAZA + "c_abf2"
EMBARGOED = BAZA + "c_f1cf"
RESTRICTED = BAZA + "c_16ec"
METADATA_ONLY = BAZA + "c_14cb"

WSZYSTKIE = (OPEN, EMBARGOED, RESTRICTED, METADATA_ONLY)


def prawo_dostepu(tryb):
    """URI COAR Access Right albo ``None``, gdy brak mapowania.

    ``tryb`` to obiekt ``Tryb_OpenAccess_Wydawnictwo_*`` (już pobrany przez
    provider) albo ``None`` — praca bez określonego trybu OpenAccess.
    Funkcja jest czysta: żadnych zapytań do bazy.

    Wartość spoza słownika COAR jest traktowana jak brak. ``AccessRight``
    jest w profilu opcjonalny, więc pominięcie elementu jest legalne, a
    przepuszczenie śmiecia wywaliłoby walidację XSD.
    """
    if tryb is None:
        return None

    uri = (tryb.coar_access_right or "").strip()
    return uri if uri in WSZYSTKIE else None
