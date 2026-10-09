"""Link do publikacji w PBN na stronie wpisu kolejki: root z uczelni.

Adres był wpisany na sztywno (``https://pbn.nauka.gov.pl/works/publication/``),
więc ignorował ``pbn_api_root`` uczelni i używał niekanonicznej ścieżki.
Źródłem uczelni jest najpierw tag wpisu kolejki (to ONA wysyłała), a gdy go
nie ma — uczelnia z adresu strony.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Uczelnia, Wydawnictwo_Ciagle
from pbn_export_queue.models import PBN_Export_Queue


@pytest.fixture
def dwie_uczelnie(db, settings):
    settings.ALLOWED_HOSTS = ["*"]
    uczelnia_a = baker.make(Uczelnia, pbn_api_root="https://pbn-a.example.com")
    uczelnia_a.site.domain = "uczelnia-a.example.com"
    uczelnia_a.site.save()
    uczelnia_b = baker.make(Uczelnia, pbn_api_root="https://pbn-b.example.com")
    return uczelnia_a, uczelnia_b


def _wpis_z_sentdata(uczelnia_wpisu, admin_user):
    from django.contrib.contenttypes.models import ContentType

    from pbn_api.models import Publication
    from pbn_api.models.sentdata import SentData

    rekord = baker.make(Wydawnictwo_Ciagle)
    publication = baker.make(Publication)
    wpis = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=rekord,
        zamowil=admin_user,
        uczelnia=uczelnia_wpisu,
    )
    baker.make(
        SentData,
        content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
        object_id=rekord.pk,
        pbn_uid=publication,
        uczelnia=uczelnia_wpisu,
    )
    return wpis, publication


def _context(client, admin_user, wpis):
    client.force_login(admin_user)
    url = reverse("pbn_export_queue:export-queue-detail", args=[wpis.pk])
    resp = client.get(url, HTTP_HOST="uczelnia-a.example.com")
    assert resp.status_code == 200
    return resp.context


@pytest.mark.django_db
def test_link_uzywa_pbn_api_root_uczelni_wpisu(client, admin_user, dwie_uczelnie):
    """Wpis otagowany uczelnią B → link do PBN-roota uczelni B."""
    _, uczelnia_b = dwie_uczelnie
    wpis, publication = _wpis_z_sentdata(uczelnia_b, admin_user)

    context = _context(client, admin_user, wpis)

    assert context["pbn_publication_url"] == (
        f"https://pbn-b.example.com/core/#/publication/view/{publication.pk}/current"
    )


@pytest.mark.django_db
def test_link_bez_tagu_uczelni_bierze_uczelnie_z_hosta(
    client, admin_user, dwie_uczelnie
):
    """Legacy wpis bez uczelni → root uczelni z adresu strony."""
    wpis, publication = _wpis_z_sentdata(None, admin_user)

    context = _context(client, admin_user, wpis)

    assert context["pbn_publication_url"] == (
        f"https://pbn-a.example.com/core/#/publication/view/{publication.pk}/current"
    )
