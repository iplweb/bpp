Naprawiono gubienie współbieżnych zmian (lost update) na singletonach statusu
optymalizacji ewaluacji. Metody ``rozpocznij()``/``zakoncz()`` modeli
``Status*`` zapisują teraz tylko pola, które faktycznie zmieniają (atomowy
``UPDATE`` po ``pk=1``), zamiast nadpisywać cały wiersz — dzięki czemu status
„w trakcie" i ``task_id`` ustawione przez współbieżne zadanie nie są już
cofane, a przycisk nie odblokowuje się przedwcześnie.
