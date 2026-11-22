"""Ustawienia z porównania z CrossRef zapisują historię rekordu w adminie."""

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.urls import reverse
from model_bakery import baker
from reversion.models import Version

from bpp.models import Autor, Rekord, Wydawnictwo_Ciagle


def _wpis(model_name, pk):
    return LogEntry.objects.get(content_type__model=model_name, object_id=str(pk))


@pytest.mark.django_db
def test_ustaw_orcid_autora_zapisuje_historie(admin_client, admin_user):
    autor = baker.make(Autor, orcid=None)

    resp = admin_client.post(
        reverse("bpp:api_ustaw_orcid"),
        {"autor": autor.pk, "orcid": "0000-0002-1825-0097"},
    )
    assert resp.json()["status"] == "ok"

    wpis = _wpis("autor", autor.pk)
    assert wpis.action_flag == CHANGE
    assert wpis.user == admin_user
    assert wpis.change_message == "Ustawiono ORCID (porównanie z CrossRef)."
    assert [w.field_dict["orcid"] for w in Version.objects.get_for_object(autor)] == [
        "0000-0002-1825-0097",
        None,
    ]


@pytest.mark.django_db
def test_ustaw_strony_zapisuje_historie(admin_client, admin_user):
    praca = baker.make(Wydawnictwo_Ciagle, strony="")
    rekord = Rekord.objects.get_for_model(praca)

    resp = admin_client.post(
        reverse("bpp:api_ustaw_strony"),
        {"rekord": rekord.form_post_pk, "strony": "447-452"},
    )
    assert resp.json()["status"] == "ok"

    wpis = _wpis("wydawnictwo_ciagle", praca.pk)
    assert wpis.user == admin_user
    assert wpis.change_message == "Ustawiono strony (porównanie z CrossRef)."
