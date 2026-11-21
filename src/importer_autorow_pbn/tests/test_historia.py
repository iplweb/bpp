"""Powiązanie autora z naukowcem PBN zapisuje historię autora w adminie."""

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.urls import reverse
from model_bakery import baker
from reversion.models import Version

from bpp.models import Autor
from importer_autorow_pbn.models import CachedScientistMatch
from pbn_api.models import Scientist


def _wpis(autor):
    return LogEntry.objects.get(content_type__model="autor", object_id=str(autor.pk))


@pytest.mark.django_db
def test_link_scientist_zapisuje_historie(client, admin_user):
    client.force_login(admin_user)
    scientist = baker.make(Scientist, mongoId="sci-hist-1")
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")

    client.post(
        reverse("importer_autorow_pbn:link_scientist", args=[scientist.mongoId]),
        {"autor_id": str(autor.pk)},
    )

    wpis = _wpis(autor)
    assert wpis.action_flag == CHANGE
    assert wpis.user == admin_user
    assert "sci-hist-1" in wpis.change_message
    wersje = Version.objects.get_for_object(autor)
    assert [w.field_dict["pbn_uid_id"] for w in wersje] == ["sci-hist-1", None]
    resp = client.get(reverse("admin:bpp_autor_history", args=[autor.pk]))
    assert "Powiązano z naukowcem PBN" in resp.content.decode()


@pytest.mark.django_db
def test_link_all_scientists_zapisuje_historie(client, admin_user, create_scientist):
    client.force_login(admin_user)
    scientist = create_scientist("sci-hist-2", lastName="Nowak", name="Anna")
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Anna")
    CachedScientistMatch.objects.filter(scientist=scientist).update(matched_autor=autor)

    resp = client.post(reverse("importer_autorow_pbn:link_all_scientists"))
    assert resp.json()["linked_count"] == 1

    wpis = _wpis(autor)
    assert wpis.user == admin_user
    assert "powiąż wszystkich" in wpis.change_message
    assert Version.objects.get_for_object(autor).count() == 2
