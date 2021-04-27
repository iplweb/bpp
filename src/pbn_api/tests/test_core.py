import pytest

from pbn_api.client import PBNClient, RequestsTransport


class TestTransport(RequestsTransport):
    def __init__(self, return_values=None):
        self.return_values = return_values

    def get(self, url, headers):
        if url in self.return_values:
            return self.return_values.get(url)
        else:
            raise ValueError(f"Brak odpowiedzi URL zdefiniowanej dla {url}")


@pytest.fixture
def pbnclient():
    transport = TestTransport()
    return PBNClient(transport=transport)


def test_RequestsTransport_get(mocker):
    m = mocker.MagicMock()
    m.status_code = 200
    rg = mocker.patch("requests.get", return_value=m)

    t = RequestsTransport("foo", "bar", "onet.pl")
    t.get("foobar", {"foo": "bar"})
    rg.assert_called_once()


def test_PBNClient_get_pages_warning():
    t = TestTransport(
        {
            "/api/v1/conferences/page?size=10": {},
        }
    )
    c = PBNClient(t)
    with pytest.warns(RuntimeWarning, match="did not return a paged"):
        c.get_conferences()


def test_PBNClient_get_conferences():
    t = TestTransport(
        {
            "/api/v1/conferences/page?size=10": {
                "content": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                "number": 0,
                "numberOfElements": 10,
                "pageable": {
                    "offset": 0,
                    "pageNumber": 0,
                    "pageSize": 10,
                    "paged": True,
                    "sort": {"sorted": False, "unsorted": True},
                    "unpaged": False,
                },
                "size": 10,
                "totalElements": 10,
                "totalPages": 1,
            },
            "/api/v1/conferences/page?size=10&page=1": {
                "content": [],
                "number": 0,
                "numberOfElements": 10,
                "pageable": {
                    "offset": 0,
                    "pageNumber": 0,
                    "pageSize": 10,
                    "paged": True,
                    "sort": {"sorted": False, "unsorted": True},
                    "unpaged": False,
                },
                "size": 10,
                "totalElements": 10,
                "totalPages": 1,
            },
        }
    )
    c = PBNClient(t)
    assert list(c.get_conferences()) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
