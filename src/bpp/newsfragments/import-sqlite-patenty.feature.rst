Nowa aplikacja ``import_sqlite``: import danych z plików SQLite generowanych
przez zewnętrzne harvestery bibliograficzne (pierwszy obsługiwany typ rekordu:
patenty). Polecenie ``import_sqlite_scan`` skanuje plik i wypisuje CSV-e do
przeglądu (unikalni twórcy z kandydatami dopasowania oraz lista rekordów),
a ``import_sqlite_apply`` — po ręcznym uzgodnieniu twórców w kolumnie
``decyzja`` — tworzy lub aktualizuje rekordy (idempotentnie po numerze prawa
wyłącznego). Dopasowanie twórców reużywa komparatora autorów BPP.
