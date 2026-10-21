"""Filtr ``link_do_pi`` a placeholder ``NiezdefiniowanaUczelnia``.

Gdy z requestu nie da się ustalić uczelni, context processor wstawia do
kontekstu placeholder (klasa bez ``pk``), a nie ``Uczelnia``. Filtr NIE może
w takiej sytuacji degradować do ``link_do_pi(None)``: metoda modelu robi
wtedy lookup ``PublikacjaInstytucji_V2`` NIE zawężony do uczelni, a dwa
wiersze na jeden ``objectId`` to w multi-install stan POPRAWNY. Efektem
byłby ``MultipleObjectsReturned`` → raport do Rollbara i mail do adminów
za link, który i tak zostanie ukryty.
"""

import uuid as uuid_module

import pytest
from model_bakery import baker

from bpp.context_processors.uczelnia import NiezdefiniowanaUczelnia
from bpp.models import Uczelnia
from bpp.templatetags.prace import link_do_pi
from pbn_api.models import Publication, PublikacjaInstytucji_V2


@pytest.mark.django_db
def test_link_do_pi_z_placeholderem_nie_robi_lookupu(mocker):
    u1 = baker.make(Uczelnia, pbn_api_root="https://pbn-u1.example.com")
    u2 = baker.make(Uczelnia, pbn_api_root="https://pbn-u2.example.com")

    objectId = Publication.objects.create(mongoId=baker.random_gen.gen_string(20))
    for uczelnia in (u1, u2):
        PublikacjaInstytucji_V2.objects.create(
            uuid=uuid_module.uuid4(),
            objectId=objectId,
            json_data={"title": "Test", "objectId": objectId.pk},
            uczelnia=uczelnia,
        )

    raport = mocker.patch("rollbar.report_message")
    mail = mocker.patch("django.core.mail.mail_admins")

    assert link_do_pi(objectId, NiezdefiniowanaUczelnia) is None

    raport.assert_not_called()
    mail.assert_not_called()
