"""HTTP transport layer for PBN API client."""

import random
import time
import warnings
from urllib.parse import quote

import requests
from requests import ConnectionError
from requests.exceptions import JSONDecodeError as RequestsJSONDecodeError
from requests.exceptions import SSLError
from simplejson.errors import JSONDecodeError

from pbn_api.const import DEFAULT_BASE_URL
from pbn_api.exceptions import (
    AccessDeniedException,
    HttpException,
    NeedsPBNAuthorisationException,
    PraceSerwisoweException,
    ResourceLockedException,
)

from .auth import OAuthMixin
from .pagination import PageableResource
from .utils import smart_content


class PBNClientTransport:
    """Base transport class for PBN API communication."""

    def __init__(self, app_id, app_token, base_url, user_token=None):
        self.app_id = app_id
        self.app_token = app_token

        self.base_url = base_url
        if self.base_url is None:
            self.base_url = DEFAULT_BASE_URL

        self.access_token = user_token


class RequestsTransport(OAuthMixin, PBNClientTransport):
    """HTTP transport implementation using requests library."""

    def _build_headers(self, headers=None):
        """Build headers for API request."""
        sent_headers = {"X-App-Id": self.app_id, "X-App-Token": self.app_token}
        if self.access_token:
            sent_headers["X-User-Token"] = self.access_token
        if headers is not None:
            sent_headers.update(headers)
        return sent_headers

    def _make_get_request_with_retry(self, url, headers, max_retries=15):
        """Make GET request with retry on SSL/Connection errors."""
        retries = 0
        while retries < max_retries:
            try:
                return requests.get(self.base_url + url, headers=headers)
            except (SSLError, ConnectionError) as e:
                retries += 1
                time.sleep(random.randint(1, 5))
                if retries >= max_retries:
                    raise e

    def _handle_403_response(self, ret, url, headers, fail_on_auth_missing):
        """Handle 403 response, attempting reauthorization if needed."""
        if fail_on_auth_missing:
            raise AccessDeniedException(url, smart_content(ret.content))

        if ret.json()["message"] in ["Access Denied", "Forbidden"]:
            raise AccessDeniedException(url, smart_content(ret.content))

        if hasattr(self, "authorize"):
            auth_result = self.authorize(self.base_url, self.app_id, self.app_token)
            if not auth_result:
                return None
            return self.get(url, headers, fail_on_auth_missing=True)

        return ret

    def _parse_json_response(self, ret, url):
        """Parse JSON response with special handling for service maintenance."""
        try:
            return ret.json()
        except (RequestsJSONDecodeError, JSONDecodeError) as e:
            if ret.status_code == 200 and b"prace serwisowe" in ret.content:
                raise PraceSerwisoweException() from e
            raise e

    def get(self, url, headers=None, fail_on_auth_missing=False):
        sent_headers = self._build_headers(headers)
        ret = self._make_get_request_with_retry(url, sent_headers)

        if ret.status_code == 403:
            result = self._handle_403_response(ret, url, headers, fail_on_auth_missing)
            if result is None:
                return
            if result != ret:
                return result

        if ret.status_code >= 400:
            raise HttpException(ret.status_code, url, smart_content(ret.content))

        return self._parse_json_response(ret, url)

    def _ensure_access_token(self):
        """Ensure access token is available."""
        if not hasattr(self, "access_token"):
            return self.authorize(self.base_url, self.app_id, self.app_token)
        return True

    def _build_post_headers(self, headers=None):
        """Build headers for POST request."""
        sent_headers = {
            "X-App-Id": self.app_id,
            "X-App-Token": self.app_token,
            "X-User-Token": self.access_token,
        }
        if headers is not None:
            sent_headers.update(headers)
        return sent_headers

    def _get_request_method(self, delete):
        """Get appropriate HTTP method."""
        return requests.delete if delete else requests.post

    def _parse_403_response(self, ret, url):
        """Parse 403 response JSON."""
        try:
            return ret.json()
        except BaseException as e:
            raise HttpException(
                ret.status_code,
                url,
                "Blad podczas odkodowywania JSON podczas odpowiedzi 403: "
                + smart_content(ret.content),
            ) from e

    def _handle_403_access_denied(self, ret_json, ret, url):
        """Handle 403 Access Denied responses."""
        from pbn_api.const import NEEDS_PBN_AUTH_MSG

        if ret_json.get("message") == "Access Denied":
            raise AccessDeniedException(url, smart_content(ret.content))

        if ret_json.get("message") == "Forbidden" and ret_json.get(
            "description", ""
        ).startswith(NEEDS_PBN_AUTH_MSG):
            raise NeedsPBNAuthorisationException(
                ret.status_code, url, smart_content(ret.content)
            )

        if hasattr(self, "authorize"):
            self.authorize(self.base_url, self.app_id, self.app_token)

    def _check_error_response(self, ret, url):
        """Check and handle error responses."""
        if ret.status_code >= 400:
            if ret.status_code == 423 and smart_content(ret.content) == "Locked":
                raise ResourceLockedException(
                    ret.status_code, url, smart_content(ret.content)
                )
            raise HttpException(ret.status_code, url, smart_content(ret.content))

    def post(self, url, headers=None, body=None, delete=False):
        if not self._ensure_access_token():
            return
        if not hasattr(self, "access_token"):
            return self.post(url, headers=headers, body=body, delete=delete)

        sent_headers = self._build_post_headers(headers)
        method = self._get_request_method(delete)
        ret = method(self.base_url + url, headers=sent_headers, json=body)

        if ret.status_code == 403:
            ret_json = self._parse_403_response(ret, url)
            self._handle_403_access_denied(ret_json, ret, url)

        self._check_error_response(ret, url)

        try:
            return ret.json()
        except (RequestsJSONDecodeError, JSONDecodeError) as e:
            if ret.status_code == 200:
                if ret.content == b"":
                    return

                if b"prace serwisowe" in ret.content:
                    raise PraceSerwisoweException() from e

            raise e

    def delete(
        self,
        url,
        headers=None,
        body=None,
    ):
        return self.post(url, headers, body, delete=True)

    def _pages(self, method, url, headers=None, body=None, page_size=10, *args, **kw):
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

        chr = "?"
        if url.find("?") >= 0:
            chr = "&"

        url = url + f"{chr}size={page_size}"
        chr = "&"

        for elem in kw:
            url += chr + elem + "=" + quote(kw[elem])

        method_function = getattr(self, method)

        if method == "get":
            res = method_function(url, headers)
        elif method == "post":
            res = method_function(url, headers, body=body)
        else:
            raise NotImplementedError

        if "pageable" not in res:
            warnings.warn(
                f"PBNClient.{method}_page request for {url} with headers {headers} "
                f"did not return a paged resource, "
                f"maybe use PBNClient.{method} (without 'page') instead",
                RuntimeWarning,
                stacklevel=2,
            )
            return res
        return PageableResource(
            self, res, url=url, headers=headers, body=body, method=method
        )

    def get_pages(self, url, headers=None, page_size=10, *args, **kw):
        return self._pages(
            "get", *args, url=url, headers=headers, page_size=page_size, **kw
        )

    def post_pages(self, url, headers=None, body=None, page_size=10, *args, **kw):
        # Jak get_pages, ale methoda to post
        if body is None:
            body = kw

        return self._pages(
            "post",
            *args,
            url=url,
            headers=headers,
            body=body,
            page_size=page_size,
            **kw,
        )
