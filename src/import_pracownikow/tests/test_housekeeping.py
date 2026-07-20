from datetime import timedelta

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.utils import timezone
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow
from import_pracownikow.tasks import usun_stare_pliki_importu_pracownikow


def _import_z_plikiem(dni_temu):
    """ImportPracownikow z zapisanym blobem, postarzony o `dni_temu` dni."""
    imp = baker.make(ImportPracownikow)
    imp.plik_xls.save("x.xlsx", ContentFile(b"dane"))
    ImportPracownikow.objects.filter(pk=imp.pk).update(
        created_on=timezone.now() - timedelta(days=dni_temu)
    )
    return imp


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


@pytest.mark.django_db
def test_task_kasuje_stare_zostawia_swieze(settings):
    """Zadanie Celery (wpięte w CELERYBEAT_SCHEDULE) kasuje bloby po retencji,
    a świeżych nie rusza."""
    settings.IMPORT_PRACOWNIKOW_RETENCJA_DNI = 90

    stary = _import_z_plikiem(dni_temu=100)
    swiezy = _import_z_plikiem(dni_temu=10)

    assert usun_stare_pliki_importu_pracownikow() == 1

    stary.refresh_from_db()
    swiezy.refresh_from_db()
    assert not stary.plik_xls
    assert swiezy.plik_xls  # świeży blob nietknięty
    # Rekordy (i historia dopasowań) zostają w obu przypadkach.
    assert ImportPracownikow.objects.filter(pk=stary.pk).exists()
    assert ImportPracownikow.objects.filter(pk=swiezy.pk).exists()


@pytest.mark.django_db
def test_task_jest_idempotentny(settings):
    """Drugie uruchomienie nie ma już czego kasować (brak podwójnego liczenia
    importów z pustym plik_xls)."""
    settings.IMPORT_PRACOWNIKOW_RETENCJA_DNI = 90
    _import_z_plikiem(dni_temu=100)

    assert usun_stare_pliki_importu_pracownikow() == 1
    assert usun_stare_pliki_importu_pracownikow() == 0
