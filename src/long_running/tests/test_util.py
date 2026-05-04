import pytest

from bpp.models import Wydawnictwo_Ciagle
from django_bpp.celery_tasks import app
from long_running.util import wait_for_object


# Zadanie do testów — zarejestrowane na poziomie modułu (celery wymaga
# rejestracji przed .apply()/.delay()).
@app.task(bind=True, name="long_running.tests.test_util._probe_wait")
def _probe_wait(self, pk, no_tries):
    wait_for_object(Wydawnictwo_Ciagle, pk, no_tries=no_tries)


@pytest.fixture
def celery_eager_retry_loops():
    """Pozwól celery zapętlić retry w eager mode.

    BPP ma globalnie ``CELERY_EAGER_PROPAGATES_EXCEPTIONS=True``
    (``app.conf.task_eager_propagates``). W eager mode tracer celery
    przy ``propagate=True`` w ``on_error`` re-raise'uje wyjątek, także
    ``Retry``. Efekt: ``apply(throw=False)`` ustawia ``propagate=False``
    TYLKO na pierwszej iteracji, ale rekurencyjne
    ``retval.sig.apply(retries=retries + 1)`` w ``Task.apply`` nie
    przenosi ``throw`` — używa domyślnego
    ``task_eager_propagates=True``, propagacja wraca, pętla się rwie
    na drugiej próbie.

    Fixture tymczasowo wyłącza ``task_eager_propagates`` na poziomie
    konfiguracji celery app, żeby wszystkie rekurencyjne ``.apply()``
    również miały ``propagate=False``. Produkcyjny worker tej
    fixture nie wymaga — tam ``Retry`` po prostu wraca do brokera
    jako re-enqueue.
    """
    prev = app.conf.task_eager_propagates
    app.conf.task_eager_propagates = False
    try:
        yield
    finally:
        app.conf.task_eager_propagates = prev


@pytest.mark.django_db
def test_wait_for_object_happy_path(wydawnictwo_ciagle):
    # Obiekt istnieje — .get() zwraca od razu, ścieżka retry nie jest
    # dotykana. Zadanie kończy się SUCCESS.
    result = _probe_wait.apply(args=(wydawnictwo_ciagle.pk, 10), throw=False)
    assert result.successful(), result.result


@pytest.mark.django_db
def test_wait_for_object_retries_and_exhausts(celery_eager_retry_loops):
    # Obiektu nigdy nie ma — celery wykonuje `no_tries` retry-ów,
    # po czym (kontrakt Task.retry z jawnym exc) podnosi oryginalny
    # DoesNotExist, a nie MaxRetriesExceededError.
    result = _probe_wait.apply(args=(999999999, 3), throw=False)
    with pytest.raises(Wydawnictwo_Ciagle.DoesNotExist):
        result.get()


@pytest.mark.django_db
def test_wait_for_object_retries_then_succeeds(
    wydawnictwo_ciagle, mocker, celery_eager_retry_loops
):
    # Symulacja wyścigu commit vs. worker: pierwsze dwa .get() udają,
    # że obiektu jeszcze nie ma, trzecie zwraca go. Dzięki celery retry
    # zadanie kończy się sukcesem.
    real_get = Wydawnictwo_Ciagle.objects.get
    calls = {"n": 0}

    def fake_get(*args, **kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise Wydawnictwo_Ciagle.DoesNotExist
        return real_get(*args, **kw)

    mocker.patch.object(Wydawnictwo_Ciagle.objects, "get", side_effect=fake_get)

    result = _probe_wait.apply(args=(wydawnictwo_ciagle.pk, 10), throw=False)
    assert result.successful(), result.result
    assert calls["n"] == 3
