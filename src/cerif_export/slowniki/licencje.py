"""Odczyt URI licencji (SPDX / Creative Commons)."""


def uri_licencji(licencja):
    """URI licencji albo ``None``, gdy nieustalone.

    ``licencja`` to obiekt ``Licencja_OpenAccess`` (już pobrany przez
    provider) albo ``None`` — praca bez wskazanej licencji. Funkcja jest
    czysta: żadnych zapytań do bazy.

    Wartości nie zgadujemy ze skrótu — skrót nie niesie wersji licencji, a
    wersja jest częścią URI. Puste pole oznacza „redakcja jeszcze nie
    potwierdziła"; wtedy element po prostu nie wychodzi.
    """
    if licencja is None:
        return None

    return (licencja.uri or "").strip() or None
