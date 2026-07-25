"""Domyślne lata w formularzu generowania metryk pochodzą z kontekstu widoku.

Wartości 2022/2025 są tu wpisane JAWNIE (a nie brane z ``OKRES_DOMYSLNY``)
celowo: test ma wykryć przypadkową zmianę okresu ewaluacyjnego, a nie
przyklepać dowolną wartość, którą akurat ma stała.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Dyscyplina_Naukowa, Uczelnia
from ewaluacja_metryki.models import MetrykaAutora


@pytest.fixture
def klient_z_metryka(admin_user, db):
    uczelnia = baker.make(Uczelnia)
    baker.make(
        MetrykaAutora,
        autor=baker.make("bpp.Autor"),
        dyscyplina_naukowa=baker.make(Dyscyplina_Naukowa, nazwa="Test Discipline"),
        jednostka=baker.make("bpp.Jednostka"),
        uczelnia=uczelnia,
        slot_maksymalny=4.0,
        slot_nazbierany=2.0,
        punkty_nazbierane=100.0,
        slot_wszystkie=3.0,
        punkty_wszystkie=150.0,
    )

    from django.contrib.auth.models import Group
    from django.test import Client

    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    admin_user.groups.add(group)

    client = Client()
    client.force_login(admin_user)
    return client


def test_formularz_generowania_ma_domyslne_lata_okresu(klient_z_metryka):
    response = klient_z_metryka.get(reverse("ewaluacja_metryki:lista"))
    assert response.status_code == 200

    assert response.context["domyslny_rok_min"] == 2022
    assert response.context["domyslny_rok_max"] == 2025

    # Bez tego szablon mógłby renderować puste ``value=""`` (literówka w
    # nazwie zmiennej kontekstu) i formularz POST-owałby pusty rok.
    html = response.content.decode()
    assert 'name="rok_min" value="2022"' in html
    assert 'name="rok_max" value="2025"' in html
