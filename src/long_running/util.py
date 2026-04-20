from celery import current_task


def wait_for_object(klass, pk, no_tries=10):
    """Pobierz obiekt z bazy albo poproś celery o ponowne uruchomienie
    bieżącego zadania za 1 sekundę.

    Przeznaczone do użycia w zadaniach celery, które startują zaraz po
    utworzeniu obiektu w innej transakcji
    (``transaction.on_commit(lambda: task.delay(pk))``): kiedy worker
    wystartuje szybciej niż commit się upropaguje, obiekt jeszcze nie
    istnieje.

    Jeżeli obiekt nie został odnaleziony, funkcja wywołuje
    ``current_task.retry(countdown=1, max_retries=no_tries)``. Celery
    w produkcji zwróci zadanie do kolejki; po ``no_tries`` nieudanych
    próbach podnosi ``MaxRetriesExceededError`` / oryginalny
    ``DoesNotExist``. Worker nie jest blokowany ``time.sleep``-em, a
    górne ograniczenie liczby prób jest egzekwowane przez framework.

    UWAGA: w trybie ``CELERY_TASK_ALWAYS_EAGER=True`` z
    ``CELERY_EAGER_PROPAGATES_EXCEPTIONS=True`` (ustawienia BPP dla
    testów) celery **nie zapętla** retry wewnątrz ``.delay().get()``,
    bo wyjątek ``Retry`` propaguje się natychmiast na zewnątrz
    ``apply()``. Żeby uruchomić prawdziwą pętlę w testach, woła się
    zadanie przez ``task.apply(args=..., throw=False)`` — wtedy
    tracer nie propaguje wyjątku i ``apply`` rekurencyjnie wywołuje
    sygnaturę zadania aż do wyczerpania ``max_retries``.

    Funkcja musi być wywoływana z kontekstu zadania celery
    (``task.delay(...)`` / ``apply_async(...)`` / ``apply(...)``).
    Wywołanie funkcji-zadania wprost (``task_func(pk)``) nie ustawia
    ``current_task`` i ominie mechanizm retry.
    """
    try:
        return klass.objects.get(pk=pk)
    except klass.DoesNotExist as exc:
        raise current_task.retry(exc=exc, countdown=1, max_retries=no_tries) from exc
