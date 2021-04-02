import warnings
from json import JSONDecodeError

import requests

from pbn_api.exceptions import PraceSerwisoweException

DEFAULT_BASE_URL = "https://pbn-micro-alpha.opi.org.pl/api"


class PBNClientTransport:
    def __init__(self, app_id, app_token, base_url, user_token=None):
        self.app_id = app_id
        self.app_token = app_token
        self.user_token = user_token

        self.base_url = base_url
        if self.base_url is None:
            self.base_url = DEFAULT_BASE_URL


class PageableResource:
    def __init__(self, transport, res, url, headers):
        self.url = url
        self.headers = headers
        self.transport = transport

        self.current_content = res["content"]
        self.current_page = res["number"]
        self.total_elements = res["totalElements"]
        self.total_pages = res["totalPages"]

        self.done = False

    def fetch_next_page(self):
        self.current_page += 1
        if self.current_page > self.total_pages:
            return
        res = self.transport.get(
            self.url + f"?page={self.current_page}", headers=self.headers
        )

        if res is not None and "content" in res:
            self.current_content = res["content"]
            return True
        else:
            self.current_content = []

    def __iter__(self):
        if self.done:
            return

        while True:
            try:
                yield self.current_content.pop(0)
            except IndexError:
                if not self.fetch_next_page():
                    self.done = True
                    return


class RequestsTransport(PBNClientTransport):
    def get(self, url, headers=None):
        sent_headers = {"X-App-Id": self.app_id, "X-App-Token": self.app_token}
        if headers is not None:
            sent_headers.update(headers)
        ret = requests.get(self.base_url + url, headers=sent_headers)
        try:
            return ret.json()
        except JSONDecodeError as e:
            if ret.status_code == 200 and b"prace serwisowe" in ret.content:
                raise PraceSerwisoweException()
            raise e

    def get_pages(self, url, headers=None):
        # Stronicowanie zwraca rezultaty w taki sposób:
        # {'content': [{'mongoId': '5e709189878c28a04737dc6f',
        #               'status': 'ACTIVE',
        # ...
        #              'versionHash': '---'}]}],
        #  'first': True,
        #  'last': False,
        #  'number': 0,
        #  'numberOfElements': 10,
        #  'pageable': {'offset': 0,
        #               'pageNumber': 0,
        #               'pageSize': 10,
        #               'paged': True,
        #               'sort': {'sorted': False, 'unsorted': True},
        #               'unpaged': False},
        #  'size': 10,
        #  'sort': {'sorted': False, 'unsorted': True},
        #  'totalElements': 68577,
        #  'totalPages': 6858}

        res = self.get(url, headers)
        if "pageable" not in res:
            warnings.warn(
                f"PBNClient.get_page request for {url} with headers {headers} did not return a paged resource, "
                f"maybe use PBNClient.get instead",
                RuntimeWarning,
            )
            return res

        return PageableResource(self, res, url, headers)


class ConferencesMixin:
    def get_conferences(self):
        return self.transport.get_pages("/v1/conferences/page")

    def get_conferences_mnisw(self):
        return self.transport.get_pages("/v1/conferences/mnisw/page")

    def get_conference(self, id):
        return self.transport.get(f"/v1/conferences/{id}")

    def get_conference_editions(self, id):
        return self.transport.get(f"/v1/conferences/{id}/editions")

    def get_conference_metadata(self, id):
        return self.transport.get(f"/v1/conferences/{id}/metadata")


class DictionariesMixin:
    def get_countries(self):
        return self.transport.get("/v1/dictionary/countries")

    def get_disciplines(self):
        return self.transport.get("/v1/dictionary/disciplines")

    def get_languages(self):
        return self.transport.get("/v1/dictionary/languages")


class PBNClient(ConferencesMixin, DictionariesMixin):
    def __init__(self, transport):
        self.transport = transport
