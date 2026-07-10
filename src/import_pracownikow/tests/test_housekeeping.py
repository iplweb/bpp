from datetime import timedelta

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.utils import timezone
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow


@pytest.mark.django_db
def test_kasuje_stary_blob_zostawia_rekord(settings):
    settings.IMPORT_PRACOWNIKOW_RETENCJA_DNI = 90
    imp = baker.make(ImportPracownikow)
    imp.plik_xls.save("x.xlsx", ContentFile(b"dane"))
    ImportPracownikow.objects.filter(pk=imp.pk).update(
        created_on=timezone.now() - timedelta(days=100)
    )
    call_command("usun_stare_pliki_importu_pracownikow")
    imp.refresh_from_db()
    assert not imp.plik_xls  # blob skasowany
    assert ImportPracownikow.objects.filter(pk=imp.pk).exists()  # rekord został
