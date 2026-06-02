Poprawka w ``sync_publication``: POST oświadczeń publikacji w trybie
selektywnym (``Uczelnia.pbn_kasuj_dyscypliny_selektywnie=True``, default)
wysyła teraz TYLKO oświadczenia brakujące w PBN (``only_in_intended``),
nie pełen zestaw lokalnych. Wcześniej kod wywoływał
``WydawnictwoPBNAdapter.pbn_get_api_statements()`` zwracające wszystkie
lokalne statements i POST-ował kompletny zestaw — także te oświadczenia,
które już były w PBN. Przy założeniu że API PBN może nie być
idempotentne (odrzucić duplikaty, utworzyć zduplikowane rekordy albo
zachowywać się nieprzewidywalnie), wysyłanie tylko brakujących jest
bezpieczniejsze — nie dublujemy żądań dla już istniejących oświadczeń,
co zachowuje ich metadata w PBN (``addedTimestamp`` itp.).

Krok 3 algorytmu (PBN puste + BPP ma) nadal wysyła wszystkie oświadczenia
publikacji, bo w tym scenariuszu ``only_in_intended`` = wszystkie klucze
lokalne. Krok 5 (tryb batch, ``pbn_kasuj_dyscypliny_selektywnie=False``)
pozostaje bez zmian — po ``delete_all`` PBN jest puste, więc POST wysyła
pełen zestaw BPP (wipe+rewrite).
