import pytest
from model_bakery import baker

from bpp.models.profile import BppUser
from orcid_integration.backends import OrcidAuthenticationBackend
from orcid_integration.models import ORCIDIdentity

from .conftest import ORCID_TEST_EMAIL, ORCID_TEST_ID


@pytest.mark.django_db
def test_authenticate_matches_by_linked_identity(
    uczelnia_with_orcid, linked_identity, bpp_user_matching_autor
):
    """Konto wybierane WYŁĄCZNIE po powiązanej tożsamości ORCID."""
    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert user is not None
    assert user.pk == bpp_user_matching_autor.pk


@pytest.mark.django_db
def test_authenticate_takeover_via_autor_email_is_blocked(
    uczelnia_with_orcid, autor_with_orcid
):
    """REPRO TAKEOVERU: redaktor ustawia w rekordzie ``Autor`` swój prawdziwy
    ORCID oraz e-mail administratora, po czym loguje się przez ORCID.

    Stary backend zwracał wtedy konto admina (match po ``Autor.email``). Teraz
    bez powiązanej ``ORCIDIdentity`` logowanie MUSI się nie udać — sam fakt, że
    istnieje ``Autor`` z tym ORCID-em i e-mailem konta, nie wystarcza.
    """
    admin = BppUser.objects.create_superuser(
        username="admin",
        password="x",
        email=ORCID_TEST_EMAIL,  # ten sam e-mail co w rekordzie autora
    )
    assert ORCIDIdentity.objects.count() == 0

    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert user is None, "Bez tożsamości ORCID logowanie nie może zwrócić konta"
    assert admin.is_superuser  # konto admina istnieje, ale nieosiągalne tą drogą


@pytest.mark.django_db
def test_authenticate_no_identity(uczelnia_with_orcid):
    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id="0000-0000-0000-0000")

    assert user is None


@pytest.mark.django_db
def test_authenticate_wrong_issuer_not_matched(uczelnia_with_orcid):
    """Tożsamość z produkcji nie loguje w środowisku sandbox (i odwrotnie)."""
    user = baker.make(BppUser)
    ORCIDIdentity.objects.create(
        user=user, issuer="https://orcid.org", sub=ORCID_TEST_ID
    )

    backend = OrcidAuthenticationBackend()
    # uczelnia_with_orcid ma orcid_sandbox=True → issuer sandbox, nie prod
    result = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert result is None


@pytest.mark.django_db
def test_authenticate_no_orcid_id(uczelnia_with_orcid):
    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=None)

    assert user is None


@pytest.mark.django_db
def test_authenticate_no_uczelnia_no_issuer(db, linked_identity):
    """Bez uczelni w requeście nie da się ustalić issuera → brak dopasowania."""
    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert user is None


@pytest.mark.django_db
def test_get_user(bpp_user_matching_autor):
    backend = OrcidAuthenticationBackend()
    user = backend.get_user(bpp_user_matching_autor.pk)

    assert user is not None
    assert user.pk == bpp_user_matching_autor.pk


@pytest.mark.django_db
def test_get_user_nonexistent(db):
    backend = OrcidAuthenticationBackend()
    user = backend.get_user(99999)

    assert user is None


@pytest.mark.django_db
def test_authenticate_inactive_user_denied(uczelnia_with_orcid, db):
    """Konto ``is_active=False`` z powiązaną tożsamością nie może się zalogować."""
    inactive = BppUser.objects.create_user(
        username="orcid_inactive",
        password="testpass123",
        email=ORCID_TEST_EMAIL,
        is_active=False,
    )
    ORCIDIdentity.objects.create(
        user=inactive, issuer="https://sandbox.orcid.org", sub=ORCID_TEST_ID
    )

    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert user is None


@pytest.mark.django_db
def test_authenticate_staff_only_blocks_regular_user(
    uczelnia_with_orcid_staff_only, linked_identity, bpp_user_matching_autor
):
    """``orcid_tylko_dla_pracownikow`` blokuje konto nie-staff."""
    assert not bpp_user_matching_autor.is_staff
    assert not bpp_user_matching_autor.is_superuser

    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert user is None


@pytest.mark.django_db
def test_authenticate_staff_only_allows_staff(
    uczelnia_with_orcid_staff_only, bpp_staff_user_matching_autor
):
    ORCIDIdentity.objects.create(
        user=bpp_staff_user_matching_autor,
        issuer="https://sandbox.orcid.org",
        sub=ORCID_TEST_ID,
    )

    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert user is not None
    assert user.pk == bpp_staff_user_matching_autor.pk


@pytest.mark.django_db
def test_authenticate_no_staff_restriction_allows_regular_user(
    uczelnia_with_orcid, linked_identity, bpp_user_matching_autor
):
    """Przy ``orcid_tylko_dla_pracownikow=False`` zwykłe konto przechodzi."""
    assert not bpp_user_matching_autor.is_staff

    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert user is not None
    assert user.pk == bpp_user_matching_autor.pk
