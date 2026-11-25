"""``visibility_timeout`` brokera Celery musi FAKTYCZNIE obowiązywać.

Ustawienie było wpisane jako ``CELERY_BROKER_TRANSPORT_OPTIONS``. Aplikacja
Celery ładuje ustawienia bez ``namespace``, więc tej nazwy nie rozpoznaje
i pomija ją bez ostrzeżenia — zamiast 6 godzin obowiązywała domyślna
1 godzina. Zadania odroczone albo czekające w rezerwie workera dłużej niż
ten limit Redis wystawia ponownie, więc wykonywały się w kilku kopiach.
"""

from unittest.mock import MagicMock

from django_bpp.celery_tasks import app
from pbn_export_queue.models import PBN_Export_Queue

GODZINA = 3600


def _visibility_timeout():
    return app.conf.broker_transport_options.get("visibility_timeout")


def test_visibility_timeout_dociera_do_celery():
    assert _visibility_timeout() == 8 * GODZINA


def test_visibility_timeout_dociera_do_kanalu_brokera():
    """To, co realnie stosuje kombu — nie tylko to, co stoi w konfiguracji."""
    with app.connection_for_read() as polaczenie:
        assert polaczenie.transport_options.get("visibility_timeout") == 8 * GODZINA


def test_visibility_timeout_przekracza_najdluzsze_odroczenie_eksportu_pbn():
    """Zadanie odroczone na dłużej niż limit wykona się w kilku kopiach.
    Najdłużej odraczane są ponowienia wycofań z PBN (rosnący odstęp)."""
    wycofanie = MagicMock(
        operacja=PBN_Export_Queue.Operacja.WYCOFANIE,
        ilosc_prob=50,
        Operacja=PBN_Export_Queue.Operacja,
    )
    najdluzszy_odstep = PBN_Export_Queue.odstep_ponowienia(wycofanie, 5 * 60)

    assert najdluzszy_odstep == 6 * GODZINA
    assert _visibility_timeout() > najdluzszy_odstep
    # RETRY_MUCH_LATER (prace serwisowe PBN) — stałe 3 godziny
    assert _visibility_timeout() > 3 * GODZINA
