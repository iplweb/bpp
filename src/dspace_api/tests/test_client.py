from unittest import mock

import pytest
from model_bakery import baker


@pytest.fixture
def fernet_key(settings):
    from cryptography.fernet import Fernet

    settings.DSPACE_CREDENTIALS_KEY = Fernet.generate_key().decode()


@pytest.mark.django_db
def test_client_authenticate_uzywa_pol_uczelni(fernet_key):
    from dspace_api.client import DSpaceClient

    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo.x/server/api"
    u.dspace_api_username = "api@x"
    u.dspace_api_password = "haslo"
    u.save()

    with mock.patch("dspace_api.client.RawDSpaceClient") as RawCls:
        raw = RawCls.return_value
        raw.authenticate.return_value = True

        client = DSpaceClient(u)
        assert client.authenticate() is True

        RawCls.assert_called_once_with(
            api_endpoint="https://repo.x/server/api",
            username="api@x",
            password="haslo",
        )


@pytest.mark.django_db
def test_client_create_item_zwraca_uuid(fernet_key):
    from dspace_api.client import DSpaceClient

    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo.x/server/api"
    u.save()

    with (
        mock.patch("dspace_api.client.RawDSpaceClient") as RawCls,
        mock.patch("dspace_api.client.Item") as ItemCls,
    ):
        raw = RawCls.return_value
        created = mock.Mock()
        created.uuid = "44444444-4444-4444-4444-444444444444"
        raw.create_item.return_value = created

        client = DSpaceClient(u)
        uuid = client.create_item(
            "55555555-5555-5555-5555-555555555555",
            {"dc.title": [{"value": "T"}]},
        )
        assert uuid == "44444444-4444-4444-4444-444444444444"
        ItemCls.assert_called_once()
        raw.create_item.assert_called_once()
