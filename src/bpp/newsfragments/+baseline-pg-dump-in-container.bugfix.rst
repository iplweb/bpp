Naprawiono generowanie ``src/baseline-sql/baseline.sql``: komenda
``baseline_rebuild`` uruchamia teraz ``pg_dump`` *wewnątrz*
testcontenera (``docker exec``) zamiast używać klienta z hosta.
Gdy host miał nowszy major PostgreSQL niż obraz bazowy
(``iplweb/bpp_dbserver:psql-16.13``), ``pg_dump`` w wersji 17
wstawiał do dumpa dyrektywę ``SET transaction_timeout = 0;``,
której PostgreSQL 16 nie zna — przez co odtworzenie baseline'u
na docelowej wersji się wywalało. Klient i serwer są teraz
zawsze w tym samym majorze. Dodatkowo scrubber wycina takie
linie jako safety net na wypadek przyszłych nowych dyrektyw.
