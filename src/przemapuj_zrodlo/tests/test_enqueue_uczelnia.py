"""Test B6 (multi-hosted): widok przemapowania źródła musi zapisywać
``uczelnia`` na wpisie kolejki eksportu PBN, pobraną z requestu.

Na instalacji multi-hosted wpis bez ``uczelnia`` failuje w czasie wysyłki
(``Uczelnia.objects.get()`` -> ``MultipleObjectsReturned``).
"""

import pytest
from model_bakery import baker

from fixtures.conftest_multisite import make_request_for_site
from pbn_export_queue.models import PBN_Export_Queue
from przemapuj_zrodlo.views import PrzemapujZrodloView


@pytest.mark.django_db
def test_enqueue_sets_uczelnia_from_request(uczelnia1, site1, settings):
    settings.ALLOWED_HOSTS = ["*"]

    user = baker.make("bpp.BppUser")
    pub = baker.make("bpp.Wydawnictwo_Ciagle")

    view = PrzemapujZrodloView()
    view.request = make_request_for_site(site1, user=user)

    sukces, bledy = view._enqueue_publikacje_to_pbn([pub])

    assert sukces == 1
    assert bledy == []

    wpis = PBN_Export_Queue.objects.filter_rekord_do_wysylki(pub).first()
    assert wpis is not None
    assert wpis.uczelnia_id == uczelnia1.pk
