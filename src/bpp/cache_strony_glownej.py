"""Unieważnianie cache'a kontekstu strony głównej (``get_uczelnia_context_data``).

DLACZEGO NIE ``get_uczelnia_context_data.invalidate()``
=======================================================

``@cached`` z cacheops buduje klucz z ARGUMENTÓW wywołania. Funkcja jest
zawsze wołana jako ``get_uczelnia_context_data(uczelnia)`` albo
``get_uczelnia_context_data(uczelnia, article_slug)``, więc bezargumentowe
``.invalidate()`` kasowało klucz wywołania zero-argumentowego, którego
nigdy nie ma — czyli NIC. Strona główna (łącznie z top-barem, bo kontekst
widoku zawiera zapamiętaną kopię obiektu ``uczelnia`` i nadpisuje tę z
context processora) serwowała stare dane do końca TTL (1h).

Wyliczanie wszystkich kluczy (każda uczelnia × każdy ``article_slug``) jest
niewykonalne, więc do klucza dokładamy GENERACJĘ (parametr ``extra``
dekoratora). Zmiana generacji unieważnia naraz wszystkie warianty — stare
wpisy zostają w Redisie, ale nikt ich już nie trafi i wygasną po TTL.
Ten sam wzorzec stosuje ``bpp.views.cache_publiczny``.

Moduł jest celowo lekki (bez importów modeli/widoków), żeby mogły go
importować sygnały w ``bpp.models`` i context processor bez cykli.
"""

from uuid import uuid4

from django.core.cache import cache
from django.db import transaction

KLUCZ_GENERACJI = "bpp:strona-glowna:generacja"


def generacja_strony_glownej(*args, **kwargs):
    """Bieżąca generacja — ``extra`` dla ``@cached`` (dostaje argumenty funkcji).

    Znacznik LOSOWY, nie licznik: eksmisja klucza z Redisa
    (``maxmemory``) nie może „cofnąć" generacji do już użytej wartości
    i wskrzesić starych wpisów.
    """
    wartosc = cache.get(KLUCZ_GENERACJI)
    if wartosc is None:
        wartosc = uuid4().hex
        cache.set(KLUCZ_GENERACJI, wartosc, None)
    return wartosc


def _wykonaj_bump():
    cache.set(KLUCZ_GENERACJI, uuid4().hex, None)


def uniewaznij_strone_glowna(*args, **kwargs):
    """Unieważnij kontekst strony głównej wszystkich uczelni (nowa generacja).

    Nadaje się wprost na receiver sygnału. Bump następuje PO zatwierdzeniu
    transakcji i najwyżej raz na transakcję:

    * ``post_save`` leci przed ``COMMIT`` — równoległe żądanie mogłoby
      zapamiętać stan sprzed zapisu już pod NOWĄ generacją na cały TTL,
    * importer zapisujący tysiące jednostek w jednym ``atomic`` robi jeden
      bump, a nie tysiące round-tripów do cache'a.
    """
    polaczenie = transaction.get_connection()
    # Skan ``run_on_commit`` zamiast własnej flagi — Django czyści tę listę
    # przy rollbacku, własna flaga przetrwałaby wycofaną transakcję.
    if any(_wykonaj_bump in wpis for wpis in polaczenie.run_on_commit):
        return
    # Poza blokiem ``atomic`` ``on_commit`` wykonuje się natychmiast.
    transaction.on_commit(_wykonaj_bump)
