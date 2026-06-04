from unittest import mock

import pytest
from django.contrib import messages
from model_bakery import baker


@pytest.mark.django_db
def test_akcja_raportuje_pominiecia():
    from dspace_api.actions import wyslij_do_dspace

    rec = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="T", rok=2024)
    modeladmin = mock.Mock()
    request = mock.Mock()
    qs = type(rec).objects.filter(pk=rec.pk)

    with mock.patch(
        "dspace_api.actions.eksportuj_rekord",
        return_value=[
            {
                "uczelnia": mock.Mock(),
                "status": "pominieto",
                "powod": "brak mapowania",
            }
        ],
    ):
        wyslij_do_dspace(modeladmin, request, qs)

    assert modeladmin.message_user.called


@pytest.mark.django_db
def test_akcja_limit_10():
    from bpp.models import Wydawnictwo_Ciagle
    from dspace_api.actions import wyslij_do_dspace

    baker.make("bpp.Wydawnictwo_Ciagle", _quantity=11)
    modeladmin = mock.Mock()
    request = mock.Mock()
    qs = Wydawnictwo_Ciagle.objects.all()

    wyslij_do_dspace(modeladmin, request, qs)
    args, kwargs = modeladmin.message_user.call_args
    assert messages.ERROR in args
