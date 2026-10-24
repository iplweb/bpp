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


@pytest.mark.django_db
def test_akcja_w_tle_kolejkuje_patenty():
    from bpp.models import Patent
    from dspace_api.actions import wyslij_do_dspace_w_tle

    p1, p2 = baker.make("bpp.Patent", _quantity=2)
    modeladmin = mock.Mock()
    request = mock.Mock()
    request.user.id = 7

    with mock.patch("dspace_api.actions.queue_dspace_export_batch") as task:
        wyslij_do_dspace_w_tle(modeladmin, request, Patent.objects.all())

    kwargs = task.delay.call_args.kwargs
    assert kwargs["app_label"] == "bpp"
    assert kwargs["model_name"] == "patent"
    assert sorted(kwargs["record_ids"]) == sorted([p1.pk, p2.pk])
