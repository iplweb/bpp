``long_running.util.wait_for_object`` nie blokuje już workera
``time.sleep``-em. W razie ``DoesNotExist`` woła
``current_task.retry(countdown=1, max_retries=no_tries)`` — celery
planuje ponowne uruchomienie tego samego zadania za sekundę, a worker
obsługuje w tym czasie inne zadania. Po wyczerpaniu prób celery
podnosi oryginalny ``DoesNotExist``. Zniknął też
``DeprecationWarning`` emitowany przy każdym wywołaniu.

Kontrakt: funkcję wywołujemy wyłącznie z kontekstu zadania celery
(``task.delay(...)``, ``.apply_async(...)``, ``.apply(...)``).
Wywołanie funkcji-zadania wprost jako zwykłej funkcji
(``task_func(pk)``) nie ustawia ``current_task`` i omija mechanizm
retry. Testy, które wcześniej wołały ``analyze_file`` i
``task_sprobuj_wyslac_do_pbn`` bezpośrednio, zostały przerobione
na wywołanie przez celery (``.delay(...).get()`` albo
``.apply(args=..., ...).get()`` — ``.apply()`` potrzebne tam, gdzie
test mockuje ``task.apply_async`` do weryfikacji re-schedulowania
i wtedy ``.delay()`` trafiłoby w mock zamiast uruchomić body
zadania).
