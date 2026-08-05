import pytest
from model_bakery import baker

from bpp.models import Autor, Uczelnia
from bpp.models.profile import BppUser

ORCID_TEST_ID = "0000-0002-1825-0097"
ORCID_TEST_EMAIL = "orcid-test@example.com"


@pytest.fixture
def uczelnia_with_orcid(db):
    return baker.make(
        Uczelnia,
        nazwa="Testowa Uczelnia",
        skrot="TU",
        orcid_client_id="APP-TESTCLIENTID1234",
        orcid_client_secret="test-secret-1234",
        orcid_sandbox=True,
    )


@pytest.fixture
def uczelnia_without_orcid(db):
    return baker.make(
        Uczelnia,
        nazwa="Uczelnia bez ORCID",
        skrot="UBO",
        orcid_client_id="",
        orcid_client_secret="",
    )


@pytest.fixture
def autor_with_orcid(db):
    return baker.make(
        Autor,
        imiona="Jan",
        nazwisko="Kowalski",
        orcid=ORCID_TEST_ID,
        email=ORCID_TEST_EMAIL,
    )


@pytest.fixture
def autor_with_orcid_no_email(db):
    return baker.make(
        Autor,
        imiona="Anna",
        nazwisko="Nowak",
        orcid="0000-0001-5109-3700",
        email="",
    )


@pytest.fixture
def bpp_user_matching_autor(db):
    return BppUser.objects.create_user(
        username="orcid_user",
        password="testpass123",
        email=ORCID_TEST_EMAIL,
    )


@pytest.fixture
def bpp_staff_user_matching_autor(db):
    return BppUser.objects.create_user(
        username="orcid_staff",
        password="testpass123",
        email=ORCID_TEST_EMAIL,
        is_staff=True,
    )


@pytest.fixture
def linked_identity(db, bpp_user_matching_autor):
    """Tożsamość ORCID powiązana z ``bpp_user_matching_autor`` w środowisku
    sandbox (``uczelnia_with_orcid`` ma ``orcid_sandbox=True``)."""
    from orcid_integration.models import ORCIDIdentity

    return ORCIDIdentity.objects.create(
        user=bpp_user_matching_autor,
        issuer="https://sandbox.orcid.org",
        sub=ORCID_TEST_ID,
    )


@pytest.fixture
def uczelnia_with_orcid_staff_only(db):
    return baker.make(
        Uczelnia,
        nazwa="Uczelnia ORCID Staff Only",
        skrot="TUSO",
        orcid_client_id="APP-TESTCLIENTID1234",
        orcid_client_secret="test-secret-1234",
        orcid_sandbox=True,
        orcid_tylko_dla_pracownikow=True,
    )
