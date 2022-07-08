from datetime import timedelta
from unittest.mock import Mock

import pytest
from model_bakery import baker

from celeryui.models import Report

from django.utils import timezone

from bpp.models import Wydawnictwo_Ciagle
from bpp.tasks import _zaktualizuj_liczbe_cytowan, remove_old_report_files


@pytest.mark.django_db
def test_remove_old_report_files():
    baker.make(Report)
    r = baker.make(Report)
    r.started_on = timezone.now() - timedelta(days=20)
    r.save()

    assert Report.objects.all().count() == 2

    remove_old_report_files()

    assert Report.objects.all().count() == 1


@pytest.mark.django_db
def test_zaktualizuj_liczbe_cytowan(uczelnia, wydawnictwo_ciagle, mocker):

    m = Mock()
    m.query_multiple = Mock(
        return_value=[{wydawnictwo_ciagle.pk: {"timesCited": "31337"}}]
    )

    mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=m)

    _zaktualizuj_liczbe_cytowan(
        [
            Wydawnictwo_Ciagle,
        ]
    )

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.liczba_cytowan == 31337
