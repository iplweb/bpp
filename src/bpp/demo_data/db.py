"""Pomocniki DB dla generatorów demo — odporność na deadlocki denorm.

Masowe INSERT-y (``bulk_create``) odpalają per-wierszowe triggery denorm,
które piszą do ``denorm_dirtyinstance``. Gdy RÓWNOLEGLE działa worker denorm
(Celery ``denorm.tasks.flush_single`` — patrz ``base.py`` routing kolejki
``denorm``), oba procesy współzawodniczą o blokadę advisory + wiersze
``denorm_dirtyinstance`` i Postgres wykrywa deadlock (SQLSTATE ``40P01``).

Deadlock jest PRZEJŚCIOWY: Postgres wycofuje jedną z transakcji-ofiar, więc
wystarczy ją powtórzyć. Generatory demo działają w autocommit (każdy
``bulk_create`` to osobna transakcja), więc powtórka jest bezpieczna —
wycofany INSERT nie zostawia połówkowych wierszy.

Reużywamy ``denorm.retry.retry_on_serialization_failure`` — biblioteka
wystawia go DOKŁADNIE na ten przypadek. Ważne: ``is_retryable`` łapie WYŁĄCZNIE
``OperationalError`` z kodem ``40001``/``40P01`` (deadlock / serialization),
więc retry NIE maskuje ``IntegrityError`` (np. naruszeń unique) ani innych
błędów danych. Dekorator jest też no-op wewnątrz ``atomic()`` (powtórka
wewnątrz zewnętrznej transakcji jest niebezpieczna — patrz docstring denorm).
"""

from __future__ import annotations

from denorm.retry import retry_on_serialization_failure


@retry_on_serialization_failure
def bulk_create_retry(manager, objs, **kwargs):
    """``manager.bulk_create(objs, **kwargs)`` odporny na deadlock/serialization.

    Zwraca to samo co ``bulk_create`` (listę z ustawionymi PK)."""
    return manager.bulk_create(objs, **kwargs)


@retry_on_serialization_failure
def retry_write(func, *args, **kwargs):
    """Owija dowolny pojedynczy zapis (np. MPTT ``rebuild()``) w retry na
    deadlock/serialization. Do użycia tam, gdzie zapis nie jest ``bulk_create``,
    ale też odpala triggery denorm (masowy UPDATE)."""
    return func(*args, **kwargs)
