"""Guard dla guarda: tracer połączeń MUSI widzieć zapis z innego wątku.

Bez tego testu tracer mógłby cicho nie działać (monkey-patch nie założony,
zdarzenia czyszczone w złym momencie) i milczenie na CI czytalibyśmy jako
„zapisów spoza głównego wątku nie ma" zamiast „nie mierzymy".
"""

import sys
import threading

import pytest


def _src_conftest():
    """Zwraca INSTANCJĘ modułu ``src/conftest.py`` załadowaną przez pytest.

    Gołe ``import conftest`` jest pod pytestem niejednoznaczne: rozstrzyga się
    na pierwszy ``conftest.py`` na ``sys.path``, a przy shardowaniu xdista bywa
    to conftest aplikacyjny (np. ``import_pracownikow/tests/conftest.py``), bez
    tracera → ``AttributeError`` na CI mimo zieleni lokalnie.

    Świeży ``importlib`` też NIE wystarcza: dałby OSOBNĄ instancję z własnym
    ``_LEAK_GUARD``, a tracer (zainstalowany przez tę właściwą instancję, bo
    ``BPP_LEAK_GUARD_STRICT`` jest ustawiony) dopisuje zdarzenia do słownika
    tamtej instancji. Musimy więc znaleźć DOKŁADNIE ten moduł, który pytest
    już załadował — po obecności ``_zainstaluj_tracer_polaczen`` w ``sys.modules``.
    """
    kandydaci = [
        m
        for m in sys.modules.values()
        if m is not None
        and (getattr(m, "__file__", "") or "")
        .replace("\\", "/")
        .endswith("/src/conftest.py")
        and hasattr(m, "_zainstaluj_tracer_polaczen")
    ]
    assert kandydaci, "nie znaleziono załadowanego src/conftest.py z tracerem"
    return kandydaci[0]


@pytest.mark.django_db
def test_tracer_widzi_polaczenie_z_innego_watku():
    conftest = _src_conftest()

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
