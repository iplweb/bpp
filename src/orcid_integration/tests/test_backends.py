import pytest

from orcid_integration.backends import OrcidAuthenticationBackend

from .conftest import ORCID_TEST_ID


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
