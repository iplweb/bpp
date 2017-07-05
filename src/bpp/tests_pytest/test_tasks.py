# -*- encoding: utf-8 -*-

from datetime import datetime, timedelta

from model_mommy import mommy
from celeryui.models import Report
import pytest

from bpp.tasks import remove_old_report_files
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
