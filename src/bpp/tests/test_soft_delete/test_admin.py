"""Faza 07: kosz w adminie — filtr, przywracanie, trwałe usuwanie, powód.

KONTRAKT PARAMETRU FILTRA: ``?is_deleted=true`` pokazuje WYŁĄCZNIE kosz,
``?is_deleted=all`` żywe razem z koszem, brak parametru — tylko żywe. Ta
sama semantyka, co w pakietowym ``SoftDeleteFilter`` (``'true'`` mapuje
tam na ``deleted_at__isnull=False``), więc parametr w URL-u nie kłamie.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_changelist_domyslnie_ukrywa_kosz(superuser_client):
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Żywa praca")
    skasowany = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    skasowany.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    resp = superuser_client.get(url)
    content = resp.content.decode("utf-8")

    assert resp.status_code == 200
    assert "Żywa praca" in content
    assert "Praca w koszu" not in content


@pytest.mark.django_db
def test_filtr_pokazuje_wylacznie_kosz(superuser_client):
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Żywa praca")
    skasowany = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    skasowany.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    resp = superuser_client.get(url, {"is_deleted": "true"})
    content = resp.content.decode("utf-8")

    assert resp.status_code == 200
    assert "Praca w koszu" in content
    assert "Żywa praca" not in content


@pytest.mark.django_db
def test_filtr_wszystkie_pokazuje_zywe_i_kosz(superuser_client):
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Żywa praca")
    skasowany = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    skasowany.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    resp = superuser_client.get(url, {"is_deleted": "all"})
    content = resp.content.decode("utf-8")

    assert resp.status_code == 200
    assert "Praca w koszu" in content
    assert "Żywa praca" in content


@pytest.mark.django_db
def test_changeform_otwiera_skasowany_rekord(superuser_client):
    """Bez ``global_objects`` w ``get_queryset`` admin dawałby 302/404 —
    a bez otwarcia rekordu nie ma jak go przywrócić ani obejrzeć."""
    skasowany = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    skasowany.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=[skasowany.pk])
    resp = superuser_client.get(url)

    assert resp.status_code == 200
