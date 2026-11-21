"""Pomocnicze dla suity ``cerif_export`` — wspólne dla kilku modułów testów.

Nie w ``conftest.py``, bo to zwykłe funkcje, nie fixtury: ``conftest``
nie jest importowalny po nazwie z poziomu testów.
"""


def strona_zywych(provider, uczelnia, **kwargs):
    """``provider.strona(...)``, ale bez nagrobków — sama ekspozycja.

    Od fazy 05b ``strona()`` paginuje NADZBIÓR (przynależność) i zwraca pary
    ``(obiekt, czy_nagrobek)``. Testy napisane wcześniej pytały o to, co
    repozytorium *wystawia*, i to pytanie nadal jest sensowne — helper
    odtwarza dokładnie dawną semantykę zwrotki, żeby nie trzeba było
    przepisywać ich asercji.

    Testy samych nagrobków wołają ``strona()`` wprost — patrz
    ``test_nagrobki.py``.
    """
    oznaczone, kursor = provider.strona(uczelnia, **kwargs)
    return [obiekt for obiekt, nagrobek in oznaczone if not nagrobek], kursor
