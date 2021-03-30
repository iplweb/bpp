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
        self.get(url, headers)
        raise NotImplementedError


class PBNClient:
    def __init__(self, transport):
        self.transport = transport

    def get_conferences(self):
        return self.transport.get_pages("/v1/conferences/page")
