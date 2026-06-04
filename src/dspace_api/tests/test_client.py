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
def test_client_create_item_zwraca_uuid_i_handle(fernet_key):
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
        created.handle = "11089/123"
        raw.create_item.return_value = created

        client = DSpaceClient(u)
        uuid, handle = client.create_item(
            "55555555-5555-5555-5555-555555555555",
            {"dc.title": [{"value": "T"}]},
        )
        assert uuid == "44444444-4444-4444-4444-444444444444"
        assert handle == "11089/123"
        ItemCls.assert_called_once()
        raw.create_item.assert_called_once()


@pytest.mark.django_db
def test_client_create_item_bez_handle_zwraca_pusty(fernet_key):
    from dspace_api.client import DSpaceClient

    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo.x/server/api"
    u.save()

    with (
        mock.patch("dspace_api.client.RawDSpaceClient") as RawCls,
        mock.patch("dspace_api.client.Item"),
    ):
        raw = RawCls.return_value
        created = mock.Mock(spec=["uuid"])  # brak atrybutu .handle
        created.uuid = "44444444-4444-4444-4444-444444444444"
        raw.create_item.return_value = created

        client = DSpaceClient(u)
        uuid, handle = client.create_item("col", {})
        assert uuid == "44444444-4444-4444-4444-444444444444"
        assert handle == ""


@pytest.mark.django_db
def test_client_fetch_handle(fernet_key):
    from dspace_api.client import DSpaceClient

    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo.x/server/api"
    u.save()

    with mock.patch("dspace_api.client.RawDSpaceClient") as RawCls:
        raw = RawCls.return_value
        item = mock.Mock()
        item.handle = "11089/999"
        raw.get_item.return_value = item

        client = DSpaceClient(u)
        assert client.fetch_handle("uuid-1") == "11089/999"
        raw.get_item.assert_called_once_with("uuid-1")


@pytest.mark.django_db
def test_client_fetch_collections(fernet_key):
    from dspace_api.client import DSpaceClient

    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo.x/server/api"
    u.save()

    with mock.patch("dspace_api.client.RawDSpaceClient") as RawCls:
        raw = RawCls.return_value
        raw.session = mock.Mock()
        raw.authenticate.return_value = True
        c1 = mock.Mock()
        c1.uuid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        c1.name = "Artykuły"
        c2 = mock.Mock()
        c2.uuid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        c2.name = "Monografie"
        raw.get_collections_iter.return_value = [c1, c2]

        client = DSpaceClient(u)
        kolekcje = client.fetch_collections(timeout=2)

        assert kolekcje == [
            {"uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "name": "Artykuły"},
            {"uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "name": "Monografie"},
        ]
        raw.authenticate.assert_called_once()


@pytest.mark.django_db
def test_client_delete_bitstream_wola_raw(fernet_key):
    from dspace_api.client import DSpaceClient

    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo.x/server/api"
    u.save()

    with mock.patch("dspace_api.client.RawDSpaceClient") as RawCls:
        raw = RawCls.return_value
        client = DSpaceClient(u)
        client.delete_bitstream("bs-uuid-1")
        assert raw.delete_bitstream.called or raw.delete_dso.called
