"""Wewnętrzne żądanie musi nieść Host zewnętrznego — inaczej Uczelnia=None,
BramkaApiV1 przepuszcza bezwarunkowo i wyciekają ukryte statusy (spec §7.2)."""

import pytest
from bpp_mcp.client import BppError

from mcp_server.klient import BppClientInProcess
from mcp_server.kontekst import DaneZadania, dane_zadania
from mcp_server.tests.utils import uruchom

pytestmark = pytest.mark.django_db(transaction=True)


def _pobierz(host, sciezka="uczelnia/"):
    async def scenariusz():
        zeton = dane_zadania.set(
            DaneZadania(
                host=host, scheme="http", ip="198.51.100.9", bearer=None, deadline=None
            )
        )
        try:
            klient = BppClientInProcess()
            return await klient.get_json(sciezka)
        finally:
            dane_zadania.reset(zeton)

    return uruchom(scenariusz)


def test_kazdy_host_widzi_swoja_uczelnie(
    settings, uczelnia1, uczelnia2, wydawnictwo_ciagle, przed_korekta
):
    """``/api/v1/uczelnia/`` NIE jest tu użyty — ``UczelniaViewSet.queryset``
    to gołe ``Uczelnia.objects.all()``, bez scoping po Site/Host (jednostki
    i uczelnie „obce" muszą być widoczne globalnie, bo autorzy afiliują się
    między instytucjami we wspólnej instalacji — patrz komentarz w
    ``JednostkaViewSet``). Sprawdzone empirycznie: oba hosty dostają
    IDENTYCZNĄ listę obu uczelni.

    Właściwością, która faktycznie różni się per Host, jest filtr
    ``ukryte_statusy("api")`` z ``UkryjStatusyKorektyMixin``
    (``api_v1/viewsets/common.py``) — on właśnie rozstrzyga uczelnię przez
    ``Uczelnia.objects.get_for_request(self.request)``, czyli przez Host
    żądania. Ukrywamy status korekty rekordu WYŁĄCZNIE dla ``uczelnia1``:
    host ``uczelnia1.localhost`` musi rekord wykluczyć, a
    ``uczelnia2.localhost`` (inna uczelnia, inna konfiguracja) — nie.
    """
    settings.ALLOWED_HOSTS = ["uczelnia1.localhost", "uczelnia2.localhost"]
    wydawnictwo_ciagle.status_korekty = przed_korekta
    wydawnictwo_ciagle.save()
    uczelnia1.ukryj_status_korekty_set.create(status_korekty=przed_korekta)

    a = _pobierz("uczelnia1.localhost", "wydawnictwo_ciagle/")
    b = _pobierz("uczelnia2.localhost", "wydawnictwo_ciagle/")
    assert a["count"] != b["count"]


def test_wylaczone_api_odmawia_takze_przez_mcp(settings, uczelnia1):
    """Dowód, że BramkaApiV1 działa na tej ścieżce."""
    settings.ALLOWED_HOSTS = ["uczelnia1.localhost"]
    uczelnia1.api_v1_wlaczone = False
    uczelnia1.save(update_fields=["api_v1_wlaczone"])
    with pytest.raises(BppError):
        _pobierz("uczelnia1.localhost")
