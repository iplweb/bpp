# Przeliczenia po aktualizacji

Część danych BPP liczy przy zapisie rekordu i trzyma w bazie (np. punktacja
dyscyplin i sloty: pole `cached_punkty_dyscyplin` i tabele
`bpp_cache_punktacja_*`). Gdy zmieniasz **sposób liczenia** takich danych,
zapisane wartości trzeba przeliczyć na każdym serwerze. BPP robi to sam po
wdrożeniu nowej wersji — wystarczy podbić wersję przeliczenia w kodzie.

## Jak to zrobić

W `src/bpp/przeliczenia.py`, w rejestrze `PRZELICZENIA`, podbij `wersja`
odpowiedniego wpisu i dopisz w komentarzu historii, czego dotyczy zmiana
(numer zgłoszenia, PR). Nowe przeliczenie = nowy wpis `Przeliczenie(nazwa=…,
wersja=1, oznacz=…)`, gdzie `oznacz` to funkcja oznaczająca rekordy do
przeliczenia i zwracająca ich liczbę — zwykle wystarczy
`oznacz_do_przeliczenia_w_denorm(model, "pole_denorm", queryset)`.

Nie pisz do tego migracji danych.

## Jak to działa

1. Worker Celery po starcie (sygnał `worker_ready`, `django_bpp/celery_tasks.py`)
   wysyła zadanie `bpp.tasks.zlec_zalegle_przeliczenia` — start workera na nic
   nie czeka.
2. Zadanie porównuje wersje z rejestru z tabelą `bpp_wersja_przeliczenia`
   (admin: „Wersje przeliczeń”). Dla zaległego przeliczenia dodaje znaczniki
   denorm (`DirtyInstance` z `func_name` = nazwa pola) partiami, każda partia
   we własnej transakcji (bez długiej transakcji blokującej triggery przy
   edycjach), a na końcu, pod blokadą wiersza (`SELECT … FOR UPDATE`), zapisuje
   nową wersję. Błąd w trakcie zostawia starą wersję — przeliczenie zostanie
   zlecone przy następnym starcie workera (wyjątek idzie do Rollbara przez
   `task_failure`); ponowne oznaczenie jest nieszkodliwe, bo istniejące
   znaczniki są pomijane. Starszy kod nie cofa zapisanej wersji.
3. Resztę robi kolejka denorm (`denorm-queue` → `flush_via_queue` →
   `flush_batch`, kolejka Celery `denorm`): partie po
   `DENORM_QUEUE_CHUNK_SIZE` rekordów, równolegle na wszystkich procesach
   workera, każdy rekord we własnej transakcji, `save(update_fields=[pole])`
   — liczone jest tylko oznaczone pole, `ostatnio_zmieniony` się nie zmienia.
   Błąd rekordu jest logowany z tracebackiem, a znacznik zostaje do ponowienia.
   Znaczniki są w bazie, więc restart w trakcie niczego nie gubi.

Postęp: `python src/manage.py denorm_show_dirtyinstances_count` (liczba
rekordów jeszcze w kolejce denorm, łącznie z bieżącymi zmianami redaktorów).

## Dlaczego start workera, a nie migracja

Przy `docker compose up` appserver robi migracje, gdy workery ze **starego**
obrazu jeszcze działają. Znaczniki dodane w migracji mógłby przeliczyć stary
kod i je skasować — wynik zostałby stary. Nowy worker startuje dopiero po
zatrzymaniu starego, więc przeliczenie zawsze liczy nowy kod. Na start
appservera (`AppConfig.ready`) też nie — to by odpalało się w każdym procesie
(gunicorn, komendy, testy).

## Testy i CI

W testach nie działa worker Celery, więc `worker_ready` nie pada i pełne
przeliczenie nie rusza. Testy mechanizmu:
`src/bpp/tests/test_models/test_sloty/test_przeliczenia.py`.

## Skutki uboczne

Przez czas przeliczenia (duża baza: kilkanaście minut – godzina) kolejka denorm
ma zaległości, więc przeliczenie pól denorm po zmianach redaktorów (np. opis
bibliograficzny w wynikach wyszukiwania) może się spóźniać, a zadania z kolejki
`celery` (raporty, eksporty) dzielą ten sam worker i mogą działać wolniej. Nocny
`denorm_rebuild --no-flush` (bpp-deploy, 22:00) i tak oznacza codziennie
wszystkie rekordy, więc obciążenie jest mniejsze niż co noc.
