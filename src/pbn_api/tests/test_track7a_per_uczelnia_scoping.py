"""Testy Track 7a: zawężanie luster PBN per-uczelnia po ``institutionId``.

Trzy modele-lustra (``OswiadczenieInstytucji``, ``OsobaZInstytucji``) niosą
PBN-owy UID instytucji w polu ``institutionId`` (FK → ``pbn_api.Institution``).
``Uczelnia`` ma ``pbn_uid`` (FK → ``pbn_api.Institution``). Stąd wiersz lustra
mapuje się na uczelnię DETERMINISTYCZNIE:

    row.institutionId_id == uczelnia.pbn_uid_id

Zawężamy zapytania/usunięcia po ``institutionId_id=uczelnia.pbn_uid_id``
(z guardem ``pbn_uid_id is not None``).
"""

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from pbn_api.models import (
    Institution,
    OswiadczenieInstytucji,
    Publication,
    Scientist,
    SentData,
)


@pytest.fixture
def institution1(db):
    return baker.make(Institution, name="Instytucja U1")


@pytest.fixture
def institution2(db):
    return baker.make(Institution, name="Instytucja U2")


@pytest.fixture
def uczelnia_pbn1(db, institution1):
    return baker.make(
        Uczelnia, skrot="P1", nazwa="Uczelnia PBN 1", pbn_uid=institution1
    )


@pytest.fixture
def uczelnia_pbn2(db, institution2):
    return baker.make(
        Uczelnia, skrot="P2", nazwa="Uczelnia PBN 2", pbn_uid=institution2
    )


@pytest.fixture
def publication(db):
    return baker.make(Publication)


# ---------------------------------------------------------------------------
# Area 1: OswiadczenieInstytucji.delete() zawęża SentData po uczelni
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_delete_oswiadczenie_scopes_sentdata_per_uczelnia(
    uczelnia_pbn1, uczelnia_pbn2, institution1, publication
):
    """Skasowanie oświadczenia U1 kasuje TYLKO SentData U1; SentData U2 żyje."""
    rec = baker.make("bpp.Wydawnictwo_Ciagle")

    sd1 = SentData.objects.create_or_update_before_upload(
        rec, {"a": 1}, uczelnia=uczelnia_pbn1
    )
    sd1.pbn_uid_id = publication.pk
    sd1.save()

    sd2 = SentData.objects.create_or_update_before_upload(
        rec, {"a": 2}, uczelnia=uczelnia_pbn2
    )
    sd2.pbn_uid_id = publication.pk
    sd2.save()

    osw = baker.make(
        OswiadczenieInstytucji,
        publicationId=publication,
        institutionId=institution1,
    )

    osw.delete()

    # SentData U1 skasowane, U2 nietknięte.
    assert not SentData.objects.filter(pk=sd1.pk).exists()
    assert SentData.objects.filter(pk=sd2.pk).exists()


@pytest.mark.django_db
def test_delete_oswiadczenie_no_local_uczelnia_global_delete(publication, institution1):
    """Gdy ``institutionId`` nie mapuje na żadną uczelnię → globalny delete."""
    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    sd = SentData.objects.create_or_update_before_upload(rec, {"a": 1}, uczelnia=None)
    sd.pbn_uid_id = publication.pk
    sd.save()

    osw = baker.make(
        OswiadczenieInstytucji,
        publicationId=publication,
        institutionId=institution1,
    )
    osw.delete()

    assert not SentData.objects.filter(pk=sd.pk).exists()


@pytest.mark.django_db
def test_delete_oswiadczenie_single_install_noop(uczelnia_pbn1, institution1):
    """Single-install: jedna uczelnia → zawężenie to no-op (kasuje swój SentData)."""
    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    publication = baker.make(Publication)
    sd = SentData.objects.create_or_update_before_upload(
        rec, {"a": 1}, uczelnia=uczelnia_pbn1
    )
    sd.pbn_uid_id = publication.pk
    sd.save()

    osw = baker.make(
        OswiadczenieInstytucji,
        publicationId=publication,
        institutionId=institution1,
    )
    osw.delete()

    assert not SentData.objects.filter(pk=sd.pk).exists()


# ---------------------------------------------------------------------------
# Area 2: download_statements_of_publication delete zawężony per-uczelnia
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_download_statements_delete_scoped_per_uczelnia(
    uczelnia_pbn1, institution1, institution2, publication
):
    """Sync U1 kasuje tylko oświadczenia U1 dla tej publikacji; U2 zostają."""
    from pbn_api.client.publication_sync import PublicationSyncMixin

    osw_u1 = baker.make(
        OswiadczenieInstytucji,
        publicationId=publication,
        institutionId=institution1,
    )
    osw_u2 = baker.make(
        OswiadczenieInstytucji,
        publicationId=publication,
        institutionId=institution2,
    )

    class FakeClient(PublicationSyncMixin):
        def __init__(self, uczelnia):
            self.uczelnia = uczelnia

        def get_institution_statements_of_single_publication(self, *a, **kw):
            return []

    client = FakeClient(uczelnia_pbn1)
    client.download_statements_of_publication(publication)

    assert not OswiadczenieInstytucji.objects.filter(pk=osw_u1.pk).exists()
    assert OswiadczenieInstytucji.objects.filter(pk=osw_u2.pk).exists()


# ---------------------------------------------------------------------------
# Area 3: integrator iteruje tylko po oświadczeniach uczelni klienta
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_usun_wszystkie_oswiadczenia_scoped(uczelnia_pbn1, institution1, institution2):
    """``usun_wszystkie_oswiadczenia`` rusza tylko oświadczenia uczelni klienta."""
    from pbn_integrator.utils.statements import usun_wszystkie_oswiadczenia

    pub1 = baker.make(Publication)
    pub2 = baker.make(Publication)
    osw_u1 = baker.make(
        OswiadczenieInstytucji, publicationId=pub1, institutionId=institution1
    )
    osw_u2 = baker.make(
        OswiadczenieInstytucji, publicationId=pub2, institutionId=institution2
    )

    deleted = []

    class FakeClient:
        uczelnia = uczelnia_pbn1

        def delete_publication_statement(self, *a, **kw):
            deleted.append(a)

    usun_wszystkie_oswiadczenia(FakeClient())

    # Tylko oświadczenie U1 zostało skasowane i wysłane do PBN.
    assert not OswiadczenieInstytucji.objects.filter(pk=osw_u1.pk).exists()
    assert OswiadczenieInstytucji.objects.filter(pk=osw_u2.pk).exists()
    assert len(deleted) == 1


@pytest.mark.django_db
def test_integruj_oswiadczenia_z_instytucji_scoped(
    uczelnia_pbn1, institution1, institution2
):
    """``integruj_oswiadczenia_z_instytucji(uczelnia=...)`` iteruje tylko po U1."""
    from pbn_integrator.utils.statements import integruj_oswiadczenia_z_instytucji

    pub1 = baker.make(Publication)
    pub2 = baker.make(Publication)
    baker.make(
        OswiadczenieInstytucji,
        publicationId=pub1,
        institutionId=institution1,
        personId=baker.make(Scientist),
    )
    baker.make(
        OswiadczenieInstytucji,
        publicationId=pub2,
        institutionId=institution2,
        personId=baker.make(Scientist),
    )

    seen = []

    import pbn_integrator.utils.statements as mod

    orig = mod.integruj_oswiadczenia_z_instytucji_pojedyncza_praca

    def spy(elem, *a, **kw):
        seen.append(elem.institutionId_id)

    mod.integruj_oswiadczenia_z_instytucji_pojedyncza_praca = spy
    try:
        integruj_oswiadczenia_z_instytucji(uczelnia=uczelnia_pbn1)
    finally:
        mod.integruj_oswiadczenia_z_instytucji_pojedyncza_praca = orig

    assert seen == [institution1.pk]


@pytest.mark.django_db
def test_integruj_oswiadczenia_z_instytucji_no_uczelnia_global(
    institution1, institution2
):
    """Bez ``uczelnia`` (legacy) iteruje po wszystkim — zachowanie globalne."""
    from pbn_integrator.utils.statements import integruj_oswiadczenia_z_instytucji

    baker.make(
        OswiadczenieInstytucji,
        institutionId=institution1,
        personId=baker.make(Scientist),
    )
    baker.make(
        OswiadczenieInstytucji,
        institutionId=institution2,
        personId=baker.make(Scientist),
    )

    seen = []
    import pbn_integrator.utils.statements as mod

    orig = mod.integruj_oswiadczenia_z_instytucji_pojedyncza_praca

    def spy(elem, *a, **kw):
        seen.append(elem.institutionId_id)

    mod.integruj_oswiadczenia_z_instytucji_pojedyncza_praca = spy
    try:
        integruj_oswiadczenia_z_instytucji()
    finally:
        mod.integruj_oswiadczenia_z_instytucji_pojedyncza_praca = orig

    assert set(seen) == {institution1.pk, institution2.pk}
