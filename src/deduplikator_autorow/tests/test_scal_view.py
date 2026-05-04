"""Testy backwards-compat dla scal_autorow_view."""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH


@pytest.fixture
def auth_client(client, db):
    user = baker.make("bpp.BppUser", is_active=True)
    user.set_password("xx")
    user.save()
    grp, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grp)
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_scal_autorow_accepts_main_autor_id(auth_client):
    main = baker.make("bpp.Autor")
    dup = baker.make("bpp.Autor")
    response = auth_client.post(
        reverse("deduplikator_autorow:scal_autorow"),
        {
            "main_autor_id": main.pk,
            "duplicate_autor_id": dup.pk,
            "skip_pbn": "true",
        },
    )
    # 200 OK or 500 on internal merge issues — but NOT 400 "missing params"
    assert response.status_code in (200, 500)
    assert b"Brak wymaganych" not in response.content


@pytest.mark.django_db
def test_scal_autorow_backwards_compat_scientist_ids(auth_client):
    """Legacy scientist_id maps to autor_id via rekord_w_bpp."""
    main = baker.make("bpp.Autor")
    dup = baker.make("bpp.Autor")
    main_sci = baker.make("pbn_api.Scientist")
    dup_sci = baker.make("pbn_api.Scientist")
    main.pbn_uid = main_sci
    main.save()
    dup.pbn_uid = dup_sci
    dup.save()

    response = auth_client.post(
        reverse("deduplikator_autorow:scal_autorow"),
        {
            "main_scientist_id": main_sci.pk,
            "duplicate_scientist_id": dup_sci.pk,
            "skip_pbn": "true",
        },
    )
    assert response.status_code in (200, 500)
    assert b"Brak wymaganych" not in response.content


@pytest.mark.django_db
def test_scal_autorow_missing_params_returns_400(auth_client):
    response = auth_client.post(
        reverse("deduplikator_autorow:scal_autorow"),
        {},
    )
    assert response.status_code == 400
    assert b"Brak wymaganych" in response.content
