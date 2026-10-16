"""Guard dla guarda: tracer połączeń MUSI widzieć zapis z innego wątku.

Bez tego testu tracer mógłby cicho nie działać (monkey-patch nie założony,
zdarzenia czyszczone w złym momencie) i milczenie na CI czytalibyśmy jako
„zapisów spoza głównego wątku nie ma" zamiast „nie mierzymy".
"""

import threading

import pytest


def _src_conftest(request):
    """Zwraca INSTANCJĘ modułu ``src/conftest.py`` załadowaną przez pytest.

    Wszystkie prostsze drogi zawodzą pod shardowaniem xdista na CI:

    - gołe ``import conftest`` rozstrzyga się na pierwszy ``conftest.py`` na
      ``sys.path`` — bywa to conftest aplikacyjny bez tracera;
    - świeży ``importlib`` daje OSOBNĄ instancję z własnym ``_LEAK_GUARD``,
      a tracer dopisuje zdarzenia do instancji załadowanej przez pytest;
    - filtr po ``__file__`` w ``sys.modules`` jest kruchy — na CI ścieżka
      bywa WZGLĘDNA (``src/conftest.py``), więc ``endswith("/src/conftest.py")``
      nie łapie.

    Deterministycznie: pytest rejestruje KAŻDY ``conftest.py`` jako plugin.
    Bierzemy ten z zarejestrowanych, który ma ``_zainstaluj_tracer_polaczen``
    — czyli dokładnie rootdir-owy ``src/conftest.py``, tę samą instancję,
    której używa runtime.
    """
    kandydaci = [
        p
        for p in request.config.pluginmanager.get_plugins()
        if hasattr(p, "_zainstaluj_tracer_polaczen")
    ]
    assert kandydaci, "nie znaleziono zarejestrowanego src/conftest.py z tracerem"
    return kandydaci[0]


@pytest.mark.django_db
def test_tracer_widzi_polaczenie_z_innego_watku(request):
    conftest = _src_conftest(request)

    conftest._zainstaluj_tracer_polaczen()
    conftest._LEAK_GUARD["zdarzenia"] = []

    def w_watku():
        from django.db import connection

        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        connection.close()

    t = threading.Thread(target=w_watku)
    t.start()
    t.join(10)

    zdarzenia = conftest._LEAK_GUARD["zdarzenia"]
    assert any("CONNECT w wątku" in z for z in zdarzenia), zdarzenia
