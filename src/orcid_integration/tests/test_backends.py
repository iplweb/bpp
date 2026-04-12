import pytest

from orcid_integration.backends import OrcidAuthenticationBackend

from .conftest import ORCID_TEST_EMAIL, ORCID_TEST_ID


@pytest.mark.django_db
def test_authenticate_by_orcid_match(autor_with_orcid, bpp_user_matching_autor):
    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert user is not None
    assert user.pk == bpp_user_matching_autor.pk


@pytest.mark.django_db
def test_authenticate_no_autor(db):
    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id="0000-0000-0000-0000")

    assert user is None


@pytest.mark.django_db
def test_authenticate_autor_no_email(autor_with_orcid_no_email):
    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id="0000-0001-5109-3700")

    assert user is None


@pytest.mark.django_db
def test_authenticate_no_matching_user(autor_with_orcid):
    """Autor exists with ORCID and email, but no BppUser has that email."""
    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert user is None


@pytest.mark.django_db
def test_authenticate_no_orcid_id():
    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=None)

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
def test_authenticate_inactive_user_denied(
    uczelnia_with_orcid, autor_with_orcid, db
):
    """is_active=False users must not be logged in."""
    from bpp.models.profile import BppUser

    inactive_user = BppUser.objects.create_user(
        username="orcid_inactive",
        password="testpass123",
        email=ORCID_TEST_EMAIL,
        is_active=False,
    )

    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert user is None
    assert inactive_user.is_active is False


@pytest.mark.django_db
def test_authenticate_active_user_allowed(
    uczelnia_with_orcid, autor_with_orcid, bpp_user_matching_autor
):
    """is_active=True users (default) are allowed."""
    assert bpp_user_matching_autor.is_active is True

    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert user is not None
    assert user.pk == bpp_user_matching_autor.pk


@pytest.mark.django_db
def test_authenticate_staff_only_blocks_regular_user(
    uczelnia_with_orcid_staff_only, autor_with_orcid, bpp_user_matching_autor
):
    """When orcid_tylko_dla_pracownikow is True, non-staff users are denied."""
    assert not bpp_user_matching_autor.is_staff
    assert not bpp_user_matching_autor.is_superuser

    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert user is None


@pytest.mark.django_db
def test_authenticate_staff_only_allows_staff(
    uczelnia_with_orcid_staff_only, autor_with_orcid, bpp_staff_user_matching_autor
):
    """When orcid_tylko_dla_pracownikow is True, staff users are allowed."""
    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert user is not None
    assert user.pk == bpp_staff_user_matching_autor.pk


@pytest.mark.django_db
def test_authenticate_staff_only_allows_superuser(
    uczelnia_with_orcid_staff_only, autor_with_orcid, db
):
    """When orcid_tylko_dla_pracownikow is True, superusers are allowed."""
    from bpp.models.profile import BppUser

    superuser = BppUser.objects.create_superuser(
        username="orcid_super",
        password="testpass123",
        email=ORCID_TEST_EMAIL,
    )

    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert user is not None
    assert user.pk == superuser.pk


@pytest.mark.django_db
def test_authenticate_no_staff_restriction_allows_regular_user(
    uczelnia_with_orcid, autor_with_orcid, bpp_user_matching_autor
):
    """When orcid_tylko_dla_pracownikow is False (default), regular users pass."""
    assert not bpp_user_matching_autor.is_staff

    backend = OrcidAuthenticationBackend()
    user = backend.authenticate(request=None, orcid_id=ORCID_TEST_ID)

    assert user is not None
    assert user.pk == bpp_user_matching_autor.pk
