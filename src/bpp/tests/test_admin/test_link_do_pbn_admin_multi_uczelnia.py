"""Repro: przycisk „PBN" nad formularzem zmian w adminie w trybie multi-homed.

Szablony ``admin/bpp/<model>/change_form.html`` wołały
``{{ original.pbn_uid.link_do_pbn }}`` — Django woła metodę bez argumentu,
więc przy >1 uczelni ``get_single_uczelnia_or_none()`` zwraca ``None``,
metoda zwraca ``None``, a przycisk dostaje dosłownie ``href="None"``.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Uczelnia, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Zrodlo


@pytest.fixture
def dwie_uczelnie(db, settings):
    settings.ALLOWED_HOSTS = ["*"]
    uczelnia_a = baker.make(Uczelnia, pbn_api_root="https://pbn-a.example.com")
    uczelnia_a.site.domain = "uczelnia-a.example.com"
    uczelnia_a.site.save()

    baker.make(Uczelnia)  # druga → single == None (multi-homed)
    return uczelnia_a


def _pobierz(admin_client, url):
    resp = admin_client.get(url, HTTP_HOST="uczelnia-a.example.com")
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert 'href="None"' not in content
    return content


@pytest.mark.parametrize("model", [Wydawnictwo_Ciagle, Wydawnictwo_Zwarte])
def test_admin_przycisk_pbn_rekordu_uzywa_uczelni_z_hosta(
    admin_client, dwie_uczelnie, model
):
    from pbn_api.models import Publication

    publication = baker.make(Publication)
    praca = baker.make(model, pbn_uid=publication)

    content = _pobierz(
        admin_client,
        reverse(f"admin:bpp_{model._meta.model_name}_change", args=(praca.pk,)),
    )
    assert (
        f"https://pbn-a.example.com/core/#/publication/view/{publication.pk}/current"
        in content
    )


@pytest.mark.parametrize("model", [Autor, Zrodlo])
def test_admin_przycisk_pbn_autora_zrodla_uzywa_uczelni_z_hosta(
    admin_client, dwie_uczelnie, model
):
    from pbn_api.models import Journal, Scientist

    pbn_model = Scientist if model is Autor else Journal
    pbn_obj = baker.make(pbn_model)
    obj = baker.make(model, pbn_uid=pbn_obj)

    content = _pobierz(
        admin_client,
        reverse(f"admin:bpp_{model._meta.model_name}_change", args=(obj.pk,)),
    )
    assert "https://pbn-a.example.com/core/#/" in content
    assert str(pbn_obj.pk) in content


def test_admin_pbn_api_publication_przycisk_pbn_uzywa_uczelni_z_hosta(
    admin_client, dwie_uczelnie
):
    from pbn_api.models import Publication

    publication = baker.make(Publication)

    content = _pobierz(
        admin_client,
        reverse("admin:pbn_api_publication_change", args=(publication.pk,)),
    )
    assert (
        f"https://pbn-a.example.com/core/#/publication/view/{publication.pk}/current"
        in content
    )
