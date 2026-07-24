"""Faza C (#438): migracja 0469 sprząta osierocony ``ContentType`` + jego
``Permission`` po usuniętym modelu Wydzial.

Test NIEPUSTY: na świeżej bazie CT ``bpp.wydzial`` nigdy nie powstaje (model
już nie istnieje), więc sam łańcuch migracji nic by nie udowodnił. Seedujemy
CT+Permission ręcznie i sprawdzamy, że funkcja migracji je kasuje — funkcja
będąca no-opem oblałaby ``test_czysci_osierocony_contenttype_i_permission``.
"""

import importlib

import pytest
from django.apps import apps as global_apps

mod = importlib.import_module("bpp.migrations.0469_faza_c_czysc_contenttype_wydzial")


@pytest.mark.django_db
def test_czysci_osierocony_contenttype_i_permission():
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    ct, _ = ContentType.objects.get_or_create(app_label="bpp", model="wydzial")
    Permission.objects.get_or_create(
        content_type=ct, codename="delete_wydzial", name="Can delete wydzial"
    )

    mod.czysc_contenttype_wydzial(global_apps, None)

    assert not ContentType.objects.filter(app_label="bpp", model="wydzial").exists()
    assert not Permission.objects.filter(content_type=ct).exists()


@pytest.mark.django_db
def test_idempotentna_gdy_nic_do_skasowania():
    # Drugi przebieg (i świeża baza bez CT) — nie rzuca, nic nie kasuje.
    mod.czysc_contenttype_wydzial(global_apps, None)
    mod.czysc_contenttype_wydzial(global_apps, None)


@pytest.mark.django_db
def test_nie_rusza_innych_contenttypow():
    from django.contrib.contenttypes.models import ContentType

    inny = ContentType.objects.filter(app_label="bpp", model="jednostka").first()
    assert inny is not None, "CT bpp.jednostka powinien istnieć"

    mod.czysc_contenttype_wydzial(global_apps, None)

    assert ContentType.objects.filter(pk=inny.pk).exists()
