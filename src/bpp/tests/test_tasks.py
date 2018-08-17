# -*- encoding: utf-8 -*-

from datetime import datetime, timedelta

from mock import Mock
from model_mommy import mommy

from bpp.models import Wydawnictwo_Ciagle
from celeryui.models import Report
import pytest

from bpp.tasks import remove_old_report_files, _zaktualizuj_liczbe_cytowan
from django.utils import timezone

@pytest.mark.django_db
def test_remove_old_report_files():
    mommy.make(Report)
    r = mommy.make(Report)
    r.started_on = timezone.now() - timedelta(days=20)
    r.save()

    assert Report.objects.all().count() == 2

    remove_old_report_files()

    assert Report.objects.all().count() == 1


@pytest.mark.django_db
def test_zaktualizuj_liczbe_cytowan(uczelnia, wydawnictwo_ciagle, mocker):

    m = Mock()
    m.query_multiple= Mock(return_value=[{wydawnictwo_ciagle.pk: {'timesCited': '31337'}}])
    fn = mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=m)

    _zaktualizuj_liczbe_cytowan([Wydawnictwo_Ciagle,])

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.liczba_cytowan == 31337
