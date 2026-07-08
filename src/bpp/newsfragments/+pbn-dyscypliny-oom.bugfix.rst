Pobieranie źródeł z PBN nie zawiesza się już na 90% (krok „Aktualizacja
brakujących dyscyplin..."). Skan dyscyplin iteruje teraz strumieniowo po
źródłach PBN (server-side cursor, tylko potrzebne kolumny) zamiast ładować
całą tabelę do pamięci — poprzednio worker Celery bywał ubijany przez OOM.
