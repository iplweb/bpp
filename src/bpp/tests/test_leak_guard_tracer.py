"""Guard dla guarda: tracer połączeń MUSI widzieć zapis z innego wątku.

Bez tego testu tracer mógłby cicho nie działać (monkey-patch nie założony,
zdarzenia czyszczone w złym momencie) i milczenie na CI czytalibyśmy jako
„zapisów spoza głównego wątku nie ma" zamiast „nie mierzymy".
"""

import threading

import pytest


@pytest.mark.django_db
def test_tracer_widzi_polaczenie_z_innego_watku():
    import conftest

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
