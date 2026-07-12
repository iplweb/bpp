"""Test B6 (multi-hosted): widok ``przemapuj_zrodlo`` musi zapisywać
``uczelnia`` na wpisie kolejki eksportu PBN, pobraną z requestu.

Na instalacji multi-hosted wpis bez ``uczelnia`` failuje w czasie wysyłki
(``Uczelnia.objects.get()`` -> ``MultipleObjectsReturned``).

Widok jest sterowany przez Django test ``Client`` (POST z ``confirm``)
z ``HTTP_HOST`` ustawionym na domenę site1 — to faktycznie przechodzi
przez middleware rozpoznający uczelnię, więc test dowodzi, że WIDOK
przekazuje uczelnię (a nie tylko że manager kolejki ją wspiera).
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from pbn_export_queue.models import PBN_Export_Queue


@pytest.mark.django_db
def test_przemapuj_zrodlo_enqueue_sets_uczelnia_from_request(
    client, uczelnia1, site1, settings, denorms
):
    settings.ALLOWED_HOSTS = ["*"]

    user = baker.make("bpp.BppUser")
    user.groups.add(Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)[0])
    client.force_login(user)

    journal_deleted = baker.make(
        "pbn_api.Journal",
        status="DELETED",
        title="Skasowana Gazeta",
        issn="1234-5678",
        eissn="",
        websiteLink="",
    )
    zrodlo_stare = baker.make(
        "bpp.Zrodlo",
        nazwa="Skasowana Gazeta",
        pbn_uid=journal_deleted,
        issn="1234-5678",
    )

    journal_active = baker.make(
        "pbn_api.Journal",
        status="ACTIVE",
        title="Skasowana Gazeta Nowa",
        issn="1234-5678",
        mniswId="12345",
        eissn="",
        websiteLink="",
    )
    zrodlo_nowe = baker.make(
        "bpp.Zrodlo",
        nazwa="Skasowana Gazeta Nowa",
        pbn_uid=journal_active,
        issn="1234-5678",
    )

    pub = baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo_stare)

    # Materializuj cache, żeby Rekord.objects.filter(zrodlo=...) widział rekord
    denorms.flush()

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo", kwargs={"zrodlo_id": zrodlo_stare.pk}
    )
    response = client.post(
        url,
        {
            "typ_wyboru": "zrodlo",
            "zrodlo_docelowe": zrodlo_nowe.pk,
            "confirm": "1",
        },
        HTTP_HOST=site1.domain,
    )

    assert response.status_code == 302

    wpis = PBN_Export_Queue.objects.filter_rekord_do_wysylki(pub).first()
    assert wpis is not None, "rekord powinien trafić do kolejki PBN"
    assert wpis.uczelnia_id == uczelnia1.pk
