"""Testy multi-hosted (audyt uczelnia, track 7b):

- write-side tagowanie ``PublikacjaInstytucji_V2.uczelnia`` w
  ``zapisz_publikacje_instytucji_v2``,
- per-uczelniane rozwiązywanie ``LinkDoPBNMixin.link_do_pi(uczelnia=...)``,
- backward-compat ``link_do_pi()`` bez uczelni (get_default),
- logika backfillu (single-install tag, multi-install NULL).
"""

import uuid as uuid_module
from urllib.parse import urlparse

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from pbn_api.models import Publication, PublikacjaInstytucji_V2


def _make_publication():
    return Publication.objects.create(mongoId=baker.random_gen.gen_string(20))


def _make_v2(objectId, uczelnia=None):
    return PublikacjaInstytucji_V2.objects.create(
        uuid=uuid_module.uuid4(),
        objectId=objectId,
        json_data={"title": "Test", "objectId": objectId.pk},
        uczelnia=uczelnia,
    )


@pytest.mark.django_db
def test_zapisz_publikacje_instytucji_v2_taguje_uczelnia(pbn_client):
    """Write-side: klient z uczelnią U1 taguje nowy wiersz _V2 uczelnią U1."""
    from pbn_integrator.utils.publications import zapisz_publikacje_instytucji_v2

    objectId = _make_publication()
    elem = {"uuid": str(uuid_module.uuid4()), "objectId": objectId.pk}

    obj, created = zapisz_publikacje_instytucji_v2(pbn_client, elem)

    assert created is True
    assert obj.uczelnia_id == pbn_client.uczelnia.pk


@pytest.mark.django_db
def test_zapisz_publikacje_instytucji_v2_brak_uczelni_nie_crashuje(pbn_client):
    """Guard: client.uczelnia == None nie wysadza zapisu (uczelnia zostaje None)."""
    from pbn_integrator.utils.publications import zapisz_publikacje_instytucji_v2

    pbn_client.uczelnia = None
    objectId = _make_publication()
    elem = {"uuid": str(uuid_module.uuid4()), "objectId": objectId.pk}

    obj, created = zapisz_publikacje_instytucji_v2(pbn_client, elem)

    assert created is True
    assert obj.uczelnia_id is None


@pytest.mark.django_db
def test_link_do_pi_per_uczelnia_rozroznia_dwa_wiersze(uczelnia):
    """Dwa wiersze _V2 dla tego samego objectId (U1, U2, różne uuid) →
    link_do_pi(U1) buduje link z pbn_api_root U1, link_do_pi(U2) z U2.
    Bez MultipleObjectsReturned."""
    site2 = baker.make("sites.Site", domain="u2.example.com")
    u1 = uczelnia
    u1.pbn_api_root = "https://pbn-u1.example.com"
    u1.save()
    u2 = baker.make(
        Uczelnia,
        skrot="U2",
        nazwa="Druga",
        site=site2,
        pbn_api_root="https://pbn-u2.example.com",
    )

    objectId = _make_publication()
    v1 = _make_v2(objectId, uczelnia=u1)
    v2 = _make_v2(objectId, uczelnia=u2)
    assert v1.pk != v2.pk

    link1 = objectId.link_do_pi(uczelnia=u1)
    link2 = objectId.link_do_pi(uczelnia=u2)

    assert link1 is not None
    assert link2 is not None
    assert urlparse(link1).hostname == "pbn-u1.example.com"
    assert str(v1.pk) in link1
    assert urlparse(link2).hostname == "pbn-u2.example.com"
    assert str(v2.pk) in link2
    assert link1 != link2


@pytest.mark.django_db
def test_link_do_pi_bez_uczelni_uzywa_get_default(uczelnia):
    """Backward-compat: link_do_pi() bez uczelni działa via get_default()."""
    uczelnia.pbn_api_root = "https://pbn-default.example.com"
    uczelnia.save()

    objectId = _make_publication()
    v = _make_v2(objectId, uczelnia=uczelnia)

    link = objectId.link_do_pi()

    assert link is not None
    assert urlparse(link).hostname == "pbn-default.example.com"
    assert str(v.pk) in link


@pytest.mark.django_db
def test_link_do_pi_z_uczelnia_bez_otagowanego_wiersza_falluje_na_versionhash(
    uczelnia,
):
    """uczelnia podana, ale brak otagowanego _V2 (pre-backfill) → DoesNotExist →
    fallback na versionHash (generyczny link), bez crasha."""
    uczelnia.pbn_api_root = "https://pbn-x.example.com"
    uczelnia.save()

    objectId = _make_publication()
    objectId.versions = [
        {"current": True, "versionHash": "abc123"},
    ]
    objectId.save()

    # wiersz _V2 otagowany INNĄ uczelnią → lookup po `uczelnia` nie znajdzie nic
    other_site = baker.make("sites.Site", domain="other.example.com")
    other = baker.make(Uczelnia, skrot="OT", nazwa="Inna", site=other_site)
    _make_v2(objectId, uczelnia=other)

    # świeży obiekt — ``current_version`` to cached_property, więc unikamy
    # zacache'owanego (pustego) stanu z chwili tworzenia.
    objectId = Publication.objects.get(pk=objectId.pk)
    link = objectId.link_do_pi(uczelnia=uczelnia)

    # degraduje do generycznego linku (versionHash), nie crashuje
    assert link is not None
    assert "abc123" in link


@pytest.mark.django_db
def test_filtr_link_do_pi_przekazuje_uczelnia(uczelnia):
    """Filtr ``link_do_pi`` z templatetags/prace przekazuje uczelnię do metody."""
    from bpp.templatetags.prace import link_do_pi as link_do_pi_filter

    uczelnia.pbn_api_root = "https://pbn-filtr.example.com"
    uczelnia.save()

    objectId = _make_publication()
    v = _make_v2(objectId, uczelnia=uczelnia)

    link = link_do_pi_filter(objectId, uczelnia)

    assert link is not None
    assert "pbn-filtr.example.com" in link
    assert str(v.pk) in link


@pytest.mark.django_db
def test_backfill_single_install_taguje_null(uczelnia):
    """Single-install: backfill taguje wiersze NULL jedyną uczelnią."""
    objectId = _make_publication()
    v = _make_v2(objectId, uczelnia=None)
    assert v.uczelnia_id is None

    # logika backfillu (mirror test_sentdata)
    assert Uczelnia.objects.count() == 1
    jedyna = Uczelnia.objects.get()
    PublikacjaInstytucji_V2.objects.filter(uczelnia__isnull=True).update(
        uczelnia=jedyna
    )

    v.refresh_from_db()
    assert v.uczelnia_id == jedyna.pk


@pytest.mark.django_db
def test_backfill_multi_install_zostawia_null(uczelnia):
    """Multi-install (≥2 uczelnie): backfill zostawia NULL (nie zgaduje)."""
    site2 = baker.make("sites.Site", domain="m2.example.com")
    baker.make(Uczelnia, skrot="M2", nazwa="Druga", site=site2)

    objectId = _make_publication()
    v = _make_v2(objectId, uczelnia=None)

    assert Uczelnia.objects.count() >= 2
    if Uczelnia.objects.count() == 1:  # nie zachodzi, ale mirror logiki migracji
        PublikacjaInstytucji_V2.objects.filter(uczelnia__isnull=True).update(
            uczelnia=Uczelnia.objects.get()
        )

    v.refresh_from_db()
    assert v.uczelnia_id is None
