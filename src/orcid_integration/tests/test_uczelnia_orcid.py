import pytest
from model_bakery import baker

from bpp.models import Uczelnia


@pytest.mark.django_db
def test_orcid_enabled_true():
    uczelnia = baker.make(
        Uczelnia,
        orcid_client_id="APP-TEST",
        orcid_client_secret="secret",
    )
    assert uczelnia.orcid_enabled is True


@pytest.mark.django_db
def test_orcid_enabled_false_no_id():
    uczelnia = baker.make(
        Uczelnia,
        orcid_client_id="",
        orcid_client_secret="secret",
    )
    assert uczelnia.orcid_enabled is False


@pytest.mark.django_db
def test_orcid_enabled_false_no_secret():
    uczelnia = baker.make(
        Uczelnia,
        orcid_client_id="APP-TEST",
        orcid_client_secret="",
    )
    assert uczelnia.orcid_enabled is False


@pytest.mark.django_db
def test_orcid_base_url_sandbox():
    uczelnia = baker.make(Uczelnia, orcid_sandbox=True)
    assert uczelnia.orcid_base_url == "https://sandbox.orcid.org"


@pytest.mark.django_db
def test_orcid_base_url_production():
    uczelnia = baker.make(Uczelnia, orcid_sandbox=False)
    assert uczelnia.orcid_base_url == "https://orcid.org"


@pytest.mark.django_db
def test_orcid_api_url_sandbox():
    uczelnia = baker.make(Uczelnia, orcid_sandbox=True)
    assert uczelnia.orcid_api_url == "https://pub.sandbox.orcid.org/v3.0"


@pytest.mark.django_db
def test_orcid_api_url_production():
    uczelnia = baker.make(Uczelnia, orcid_sandbox=False)
    assert uczelnia.orcid_api_url == "https://pub.orcid.org/v3.0"
