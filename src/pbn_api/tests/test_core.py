import pytest

from pbn_api.core import PBNClient, RequestsTransport


class TestTransport:
    def __init__(self, return_values=None):
        self.return_values = return_values

    def get(self, url, headers):
        if url in self.return_values:
            return self.return_values.get(url)


@pytest.fixture
def pbnclient():
    transport = TestTransport()
    return PBNClient(transport=transport)


def test_RequestsTransport_get(mocker):
    rg = mocker.patch("requests.get")
    t = RequestsTransport("foo", "bar", "onet.pl")
    t.get("foobar", {"foo": "bar"})
    rg.assert_called_once()


def test_PBNClient_get_conferences():
    # t = TestTransport({"/v1/conferences/page": []})
    raise NotImplementedError
