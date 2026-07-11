Nowa aplikacja ``import_sqlite``: import patentów z bazy SQLite formatu
ppm_harvester. Polecenie ``import_sqlite_scan`` skanuje plik i wypisuje CSV-e
do przeglądu (unikalni twórcy z kandydatami dopasowania oraz lista patentów),
a ``import_sqlite_apply`` — po ręcznym uzgodnieniu twórców w kolumnie
``decyzja`` — tworzy lub aktualizuje rekordy patentów (idempotentnie po numerze
prawa wyłącznego). Dopasowanie twórców reużywa komparatora autorów BPP.
