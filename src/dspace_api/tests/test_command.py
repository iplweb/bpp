from unittest import mock

import pytest
from django.core.management import call_command
from model_bakery import baker


@pytest.mark.django_db
def test_command_wola_eksport_dla_id():
    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    with mock.patch(
        "dspace_api.management.commands.dspace_wyslij.eksportuj_rekord",
        return_value=[],
    ) as m:
        call_command("dspace_wyslij", "wydawnictwo_ciagle", str(rec.id))
    assert m.called
