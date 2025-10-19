import json
import random
import sys
import time
import warnings
from builtins import NotImplementedError
from pprint import pprint
from urllib.parse import parse_qs, quote, urlparse

import requests
import rollbar
from django.contrib.contenttypes.models import ContentType
from django.core.mail import mail_admins
from django.db import transaction
from django.db.models import Model
from django.utils.itercompat import is_iterable
from requests import ConnectionError
from requests.exceptions import JSONDecodeError as RequestsJSONDecodeError
from requests.exceptions import SSLError
from simplejson.errors import JSONDecodeError

from import_common.core import (
    matchuj_aktualna_dyscypline_pbn,
    matchuj_nieaktualna_dyscypline_pbn,
)
from import_common.normalization import normalize_kod_dyscypliny
from pbn_api.adapters.wydawnictwo import (
    OplataZaWydawnictwoPBNAdapter,
    WydawnictwoPBNAdapter,
)
from pbn_api.const import (
    DEFAULT_BASE_URL,
    NEEDS_PBN_AUTH_MSG,
    PBN_DELETE_PUBLICATION_STATEMENT,
    PBN_GET_DISCIPLINES_URL,
    PBN_GET_INSTITUTION_PUBLICATIONS_V2,
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_GET_JOURNAL_BY_ID,
    PBN_GET_LANGUAGES_URL,
    PBN_GET_PUBLICATION_BY_ID_URL,
    PBN_POST_INSTITUTION_STATEMENTS_URL,
    PBN_POST_PUBLICATION_FEE_URL,
    PBN_POST_PUBLICATION_NO_STATEMENTS_URL,
    PBN_POST_PUBLICATIONS_URL,
    PBN_SEARCH_PUBLICATIONS_URL,
)
from pbn_api.exceptions import (
    AccessDeniedException,
    AuthenticationConfigurationError,
    AuthenticationResponseError,
    CannotDeleteStatementsException,
    HttpException,
    NeedsPBNAuthorisationException,
    NoFeeDataException,
    NoPBNUIDException,
    PBNUIDChangedException,
    PBNUIDSetToExistentException,
    PraceSerwisoweException,
    PublikacjaInstytucjiV2NieZnalezionaException,
    ResourceLockedException,
    SameDataUploadedRecently,
    ZnalezionoWielePublikacjiInstytucjiV2Exception,
)
from pbn_api.models import TlumaczDyscyplin
from pbn_api.models.discipline import Discipline, DisciplineGroup
from pbn_api.models.pbn_odpowiedzi_niepozadane import PBNOdpowiedziNiepozadane
from pbn_api.models.sentdata import SentData
from pbn_api.utils import rename_dict_key


def smart_content(content):
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content


class PBNClientTransport:
    def __init__(self, app_id, app_token, base_url, user_token=None):
        self.app_id = app_id
        self.app_token = app_token

        self.base_url = base_url
        if self.base_url is None:
            self.base_url = DEFAULT_BASE_URL

        self.access_token = user_token


class PageableResource:
    def __init__(self, transport, res, url, headers, body=None, method="get"):
        self.url = url
        self.headers = headers
        self.transport = transport
        self.body = body
        self.method = getattr(transport, method)

        try:
            self.page_0 = res["content"]
        except KeyError:
            self.page_0 = []

        self.current_page = res["number"]
        self.total_elements = res["totalElements"]
        self.total_pages = res["totalPages"]
        self.done = False

    def count(self):
        return self.total_elements

    def fetch_page(self, current_page):
        if current_page == 0:
            return self.page_0
        # print(f"FETCH {current_page}")

        kw = {"headers": self.headers}
        if self.body:
            kw["body"] = self.body

        ret = self.method(self.url + f"&page={current_page}", **kw)
        # print(f"FETCH DONE {current_page}")

        try:
            return ret["content"]
        except KeyError:
            return

    def __iter__(self):
        for n in range(0, self.total_pages):
            yield from self.fetch_page(n)


class OAuthMixin:
    @classmethod
    def get_auth_url(klass, base_url, app_id, state=None):
        url = f"{base_url}/auth/pbn/api/registration/user/token/{app_id}"
        if state:
            from urllib.parse import quote

            url += f"?state={quote(state)}"
        return url

    @classmethod
    def get_user_token(klass, base_url, app_id, app_token, one_time_token):
        headers = {
            "X-App-Id": app_id,
            "X-App-Token": app_token,
        }
        body = {"oneTimeToken": one_time_token}
        url = f"{base_url}/auth/pbn/api/user/token"
        response = requests.post(url=url, json=body, headers=headers)
        try:
            response.json()
        except ValueError as e:
            if response.content.startswith(b"Mismatched X-APP-TOKEN: "):
                raise AuthenticationConfigurationError(
                    "Token aplikacji PBN nieprawidłowy. Poproś administratora "
                    "o skonfigurowanie prawidłowego tokena aplikacji PBN w "
                    "ustawieniach obiektu Uczelnia. "
                ) from e

            raise AuthenticationResponseError(response.content) from e

        return response.json().get("X-User-Token")

    def authorize(self, base_url, app_id, app_token):
        from pbn_api.conf import settings

        if self.access_token:
            return True

        self.access_token = getattr(settings, "PBN_CLIENT_USER_TOKEN", None)
        if self.access_token:
            return True

        auth_url = OAuthMixin.get_auth_url(base_url, app_id)

        print(
            f"""I have launched a web browser with {auth_url} ,\nplease log-in,
             then paste the redirected URL below. \n"""
        )
        import webbrowser

        webbrowser.open(auth_url)
        redirect_response = input("Paste the full redirect URL here:")
        one_time_token = parse_qs(urlparse(redirect_response).query).get("ott")[0]
        print("ONE TIME TOKEN", one_time_token)

        self.access_token = OAuthMixin.get_user_token(
            base_url, app_id, app_token, one_time_token
        )

        print("ACCESS TOKEN", self.access_token)
        return True


class RequestsTransport(OAuthMixin, PBNClientTransport):
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
                    # open("pbn_client_dump.html", "wb").write(ret.content)
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
                f"PBNClient.{method}_page request for {url} with headers {headers} did not return a paged resource, "
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


class ConferencesMixin:
    def get_conferences(self, *args, **kw):
        return self.transport.get_pages("/api/v1/conferences/page", *args, **kw)

    def get_conferences_mnisw(self, *args, **kw):
        return self.transport.get_pages("/api/v1/conferences/mnisw/page", *args, **kw)

    def get_conference(self, id):
        return self.transport.get(f"/api/v1/conferences/{id}")

    def get_conference_editions(self, id):
        return self.transport.get(f"/api/v1/conferences/{id}/editions")

    def get_conference_metadata(self, id):
        return self.transport.get(f"/api/v1/conferences/{id}/metadata")


class DictionariesMixin:
    def get_countries(self):
        return self.transport.get("/api/v1/dictionary/countries")
        return self.transport.get("/api/v1/dictionary/countries")

    def get_disciplines(self):
        return self.transport.get(PBN_GET_DISCIPLINES_URL)

    def get_languages(self):
        return self.transport.get(PBN_GET_LANGUAGES_URL)


class InstitutionsMixin:
    def get_institutions(self, status="ACTIVE", *args, **kw):
        return self.transport.get_pages(
            "/api/v1/institutions/page", *args, status=status, **kw
        )

    def get_institution_by_id(self, id):
        return self.transport.get(f"/api/v1/institutions/{id}")

    def get_institution_by_version(self, version):
        return self.transport.get_pages(f"/api/v1/institutions/version/{version}")

    def get_institution_metadata(self, id):
        return self.transport.get_pages(f"/api/v1/institutions/{id}/metadata")

    def get_institutions_polon(self, includeAllVersions="true", *args, **kw):
        return self.transport.get_pages(
            "/api/v1/institutions/polon/page",
            *args,
            includeAllVersions=includeAllVersions,
            **kw,
        )

    def get_institutions_polon_by_uid(self, uid):
        return self.transport.get(f"/api/v1/institutions/polon/uid/{uid}")

    def get_institutions_polon_by_id(self, id):
        return self.transport.get(f"/api/v1/institutions/polon/{id}")


class InstitutionsProfileMixin:
    def get_institution_publications(self, page_size=10) -> PageableResource:
        return self.transport.get_pages(
            "/api/v1/institutionProfile/publications/page", page_size=page_size
        )

    def get_institution_publications_v2(
        self,
    ) -> PageableResource:
        return self.transport.get_pages(PBN_GET_INSTITUTION_PUBLICATIONS_V2)

    def get_institution_statements(self, page_size=10):
        return self.transport.get_pages(
            PBN_GET_INSTITUTION_STATEMENTS,
            page_size=page_size,
        )

    def get_institution_statements_of_single_publication(
        self, pbn_uid_id, page_size=50
    ):
        return self.transport.get_pages(
            PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=" + pbn_uid_id,
            page_size=page_size,
        )

    def get_institution_publication_v2(
        self,
        objectId,
    ):
        return self.transport.get_pages(
            PBN_GET_INSTITUTION_PUBLICATIONS_V2 + f"?publicationId={objectId}",
        )

    def delete_all_publication_statements(self, publicationId):
        url = PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=publicationId)
        try:
            return self.transport.delete(
                url,
                body={"all": True, "statementsOfPersons": []},
            )
        except HttpException as e:
            if e.status_code != 400 or not e.url.startswith(url):
                raise e

            try:
                ret_json = json.loads(e.content)
            except BaseException as parse_err:
                raise e from parse_err
            ZABLOKOWANE = "zostało tymczasowo zablokowane z uwagi na równoległą operację. Prosimy spróbować ponownie."
            NIE_MOZNA_USUNAC = "Nie można usunąć oświadczeń."
            NIE_ISTNIEJA = "Nie istnieją oświadczenia dla publikacji"
            NIE_ISTNIEJE = "Nie istnieje oświadczenie dla publikacji"

            if ret_json:
                if e.json.get("message") == "Locked" and ZABLOKOWANE in e.content:
                    raise ResourceLockedException(e.content) from e

                try:
                    try:
                        msg = e.json["details"]["publicationId"]
                    except KeyError:
                        msg = e.json["details"][f"publicationId.{publicationId}"]

                    if (
                        NIE_ISTNIEJA in msg or NIE_ISTNIEJE in msg
                    ) and NIE_MOZNA_USUNAC in msg:
                        # Opis odpowiada sytuacji "Nie można usunąć oświadczeń, nie istnieją"
                        raise CannotDeleteStatementsException(e.content)

                except (TypeError, KeyError) as key_err:
                    if (
                        NIE_ISTNIEJA in e.content or NIE_ISTNIEJE in e.content
                    ) and NIE_MOZNA_USUNAC in e.content:
                        raise CannotDeleteStatementsException(e.content) from key_err

            raise e

    def delete_publication_statement(self, publicationId, personId, role):
        return self.transport.delete(
            PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=publicationId),
            body={"statementsOfPersons": [{"personId": personId, "role": role}]},
        )

    def post_discipline_statements(self, statements_data):
        """
        Send discipline statements to PBN API.

        Args:
            statements_data (list): List of statement dictionaries containing discipline information

        Returns:
            dict: Response from PBN API
        """
        return self.transport.post(
            PBN_POST_INSTITUTION_STATEMENTS_URL, body=statements_data
        )


class JournalsMixin:
    def get_journals_mnisw(self, *args, **kw):
        return self.transport.get_pages("/api/v1/journals/mnisw/page", *args, **kw)

    def get_journals_mnisw_v2(self, *args, **kw):
        return self.transport.get_pages("/api/v2/journals/mnisw/page", *args, **kw)

    def get_journals(self, *args, **kw):
        return self.transport.get_pages("/api/v1/journals/page", *args, **kw)

    def get_journals_v2(self, *args, **kw):
        return self.transport.get_pages("/api/v2/journals/page", *args, **kw)

    def get_journal_by_version(self, version):
        return self.transport.get(f"/api/v1/journals/version/{version}")

    def get_journal_by_id(self, id):
        return self.transport.get(PBN_GET_JOURNAL_BY_ID.format(id=id))

    def get_journal_metadata(self, id):
        return self.transport.get(f"/api/v1/journals/{id}/metadata")


class PersonMixin:
    def get_people_by_institution_id(self, id):
        return self.transport.get(f"/api/v1/person/institution/{id}")

    def get_person_by_natural_id(self, id):
        return self.transport.get(f"/api/v1/person/natural/{id}")

    def get_person_by_orcid(self, orcid):
        return self.transport.get(f"/api/v1/person/orcid/{orcid}")

    def get_people(self, *args, **kw):
        return self.transport.get_pages("/api/v1/person/page", *args, **kw)

    def get_person_by_polon_uid(self, uid):
        return self.transport.get(f"/api/v1/person/polon/{uid}")

    def get_person_by_version(self, version):
        return self.transport.get(f"/api/v1/person/version/{version}")

    def get_person_by_id(self, id):
        return self.transport.get(f"/api/v1/person/{id}")


class PublishersMixin:
    def get_publishers_mnisw(self, *args, **kw):
        return self.transport.get_pages("/api/v1/publishers/mnisw/page", *args, **kw)

    def get_publishers_mnisw_yearlist(self, *args, **kw):
        return self.transport.get_pages(
            "/api/v1/publishers/mnisw/page/yearlist", *args, **kw
        )

    def get_publishers(self, *args, **kw):
        return self.transport.get_pages("/api/v1/publishers/page", *args, **kw)

    def get_publisher_by_version(self, version):
        return self.transport.get(f"/api/v1/publishers/version/{version}")

    def get_publisher_by_id(self, id):
        return self.transport.get(f"/api/v1/publishers/{id}")

    def get_publisher_metadata(self, id):
        return self.transport.get(f"/api/v1/publishers/{id}/metadata")


class PublicationsMixin:
    def get_publication_by_doi(self, doi):
        return self.transport.get(
            f"/api/v1/publications/doi/?doi={quote(doi, safe='')}",
        )

    def get_publication_by_doi_page(self, doi):
        return self.transport.get_pages(
            f"/api/v1/publications/doi/page?doi={quote(doi, safe='')}",
            headers={"doi": doi},
        )

    def get_publication_by_id(self, id):
        return self.transport.get(PBN_GET_PUBLICATION_BY_ID_URL.format(id=id))

    def get_publication_metadata(self, id):
        return self.transport.get(f"/api/v1/publications/id/{id}/metadata")

    def get_publications(self, **kw):
        return self.transport.get_pages("/api/v1/publications/page", **kw)

    def get_publication_by_version(self, version):
        return self.transport.get(f"/api/v1/publications/version/{version}")


class SearchMixin:
    def search_publications(self, *args, **kw):
        return self.transport.post_pages(PBN_SEARCH_PUBLICATIONS_URL, body=kw)


class PBNClient(
    ConferencesMixin,
    DictionariesMixin,
    InstitutionsMixin,
    InstitutionsProfileMixin,
    JournalsMixin,
    PersonMixin,
    PublicationsMixin,
    PublishersMixin,
    SearchMixin,
):
    _interactive = False

    def __init__(self, transport: RequestsTransport):
        self.transport = transport

    def post_publication(self, json):
        return self.transport.post(PBN_POST_PUBLICATIONS_URL, body=json)

    def convert_js_with_statements_to_no_statements(self, json):
        # PBN zmienił givenNames na firstName
        for elem in json.get("authors", []):
            elem["firstName"] = elem.pop("givenNames")

        for elem in json.get("editors", []):
            elem["firstName"] = elem.pop("givenNames")

        # PBN życzy abstrakty w root
        abstracts = json.pop("languageData", {}).get("abstracts", [])
        if abstracts:
            json["abstracts"] = abstracts

        # PBN nie życzy opłat
        json.pop("fee", None)

        # PBN zmienił nazwę mniswId na ministryId
        json = rename_dict_key(json, "mniswId", "ministryId")

        # OpenAccess modeArticle -> mode
        json = rename_dict_key(json, "modeArticle", "mode")

        # OpenAccess releaseDateYear "2022" -> 2022
        if json.get("openAccess", False):
            if isinstance(json["openAccess"], dict) and json["openAccess"].get(
                "releaseDateYear"
            ):
                try:
                    i = int(json["openAccess"]["releaseDateYear"])
                except (ValueError, TypeError, AttributeError):
                    pass

                json["openAccess"]["releaseDateYear"] = i
        return json

    def post_publication_no_statements(self, json):
        """
        Ta funkcja służy do wysyłania publikacji BEZ oświadczeń.

        Bierzemy słownik JSON z publikacji-z-oświadczeniami i przetwarzamy go.

        :param json:
        :return:
        """
        return self.transport.post(PBN_POST_PUBLICATION_NO_STATEMENTS_URL, body=[json])

    def post_publication_fee(self, publicationId, json):
        return self.transport.post(
            PBN_POST_PUBLICATION_FEE_URL.format(id=publicationId), body=json
        )

    def get_publication_fee(self, publicationId):
        res = self.transport.post_pages(
            "/api/v1/institutionProfile/publications/search/fees",
            body={"publicationIds": [str(publicationId)]},
        )
        if not res.count():
            return
        elif res.count() == 1:
            return list(res)[0]
        else:
            raise NotImplementedError("count > 1")

    def _prepare_publication_json(self, rec, export_pk_zero, always_affiliate_to_uid):
        """Prepare publication JSON data."""
        js = WydawnictwoPBNAdapter(
            rec,
            export_pk_zero=export_pk_zero,
            always_affiliate_to_uid=always_affiliate_to_uid,
        ).pbn_get_json()

        bez_oswiadczen = "statements" not in js
        if bez_oswiadczen:
            js = self.convert_js_with_statements_to_no_statements(js)

        return js, bez_oswiadczen

    def _check_upload_needed(self, rec, js, force_upload):
        """Check if upload is needed."""
        if not force_upload:
            needed = SentData.objects.check_if_upload_needed(rec, js)
            if not needed:
                raise SameDataUploadedRecently(
                    SentData.objects.get_for_rec(rec).last_updated_on
                )

    def _post_publication_data(self, js, bez_oswiadczen):
        """Post publication data and extract objectId."""
        if not bez_oswiadczen:
            ret = self.post_publication(js)
            objectId = ret.get("objectId", None)
        else:
            ret = self.post_publication_no_statements(js)
            if len(ret) != 1:
                raise Exception(
                    "Lista zwróconych obiektów przy wysyłce pracy bez oświadczeń różna od jednego. "
                    "Sytuacja nieobsługiwana, proszę o kontakt z autorem programu. "
                )
            try:
                objectId = ret[0].get("id", None)
            except KeyError as e:
                raise Exception(
                    f"Serwer zwrócił nieoczekiwaną odpowiedź. {ret=}"
                ) from e

        return ret, objectId

    def _should_retry_validation_error(self, e):
        """Check if HTTP exception is a retryable validation error."""
        return (
            e.status_code == 400
            and e.url == "/api/v1/publications"
            and "Bad Request" in e.content
            and "Validation failed." in e.content
        )

    def _retry_download_publication(self, objectId):
        """Attempt to download publication data after validation error."""
        try:
            publication = self.download_publication(objectId=objectId)
            self.download_statements_of_publication(publication)
            self.pobierz_publikacje_instytucji_v2(objectId=objectId)
        except Exception:
            pass

    def upload_publication(
        self,
        rec,
        force_upload=False,
        export_pk_zero=None,
        always_affiliate_to_uid=None,
        max_retries_on_validation_error=3,
    ):
        """
        Ta funkcja wysyła dane publikacji na serwer, w zależności od obecności oświadczeń
        w JSONie (klucz: "statements") używa albo api /v1/ do wysyłki publikacji "ze wszystkim",
        albo korzysta z api /v1/ repozytorialnego.

        Zwracane wyniki wyjściowe też różnią się w zależnosci od użytego API stąd też ta funkcja
        stara się w miarę rozsądnie to ogarnąć.
        """
        js, bez_oswiadczen = self._prepare_publication_json(
            rec, export_pk_zero, always_affiliate_to_uid
        )
        self._check_upload_needed(rec, js, force_upload)

        # Create or update SentData record BEFORE API call
        sent_data = SentData.objects.create_or_update_before_upload(rec, js)  # noqa

        retry_count = max_retries_on_validation_error
        ret = None
        objectId = None

        while True:
            try:
                ret, objectId = self._post_publication_data(js, bez_oswiadczen)
                SentData.objects.mark_as_successful(
                    rec, pbn_uid_id=objectId, api_response_status=str(ret)
                )
                break

            except HttpException as e:
                if self._should_retry_validation_error(e):
                    retry_count -= 1
                    if retry_count <= 0:
                        SentData.objects.mark_as_failed(
                            rec, exception=str(e), api_response_status=e.content
                        )
                        raise e

                    time.sleep(0.5)
                    self._retry_download_publication(objectId)
                    continue

                SentData.objects.mark_as_failed(
                    rec, exception=str(e), api_response_status=e.content
                )
                raise e

            except Exception as e:
                SentData.objects.mark_as_failed(rec, exception=str(e))
                raise e

        return objectId, ret, js, bez_oswiadczen

    def download_publication(self, doi=None, objectId=None):
        from pbn_integrator.utils import zapisz_mongodb

        from .models import Publication

        assert doi or objectId

        if doi:
            data = self.get_publication_by_doi(doi)
        elif objectId:
            data = self.get_publication_by_id(objectId)

        return zapisz_mongodb(data, Publication)

    @transaction.atomic
    def download_statements_of_publication(self, pub):
        from pbn_api.models import OswiadczenieInstytucji
        from pbn_integrator.utils import pobierz_mongodb, zapisz_oswiadczenie_instytucji

        OswiadczenieInstytucji.objects.filter(publicationId_id=pub.pk).delete()

        pobierz_mongodb(
            self.get_institution_statements_of_single_publication(pub.pk, 5120),
            None,
            fun=zapisz_oswiadczenie_instytucji,
            client=self,
            disable_progress_bar=True,
        )

    def pobierz_publikacje_instytucji_v2(self, objectId):
        from pbn_integrator.utils import zapisz_publikacje_instytucji_v2

        elem = list(self.get_institution_publication_v2(objectId=objectId))
        if not elem:
            raise PublikacjaInstytucjiV2NieZnalezionaException(objectId)

        if len(elem) != 1:
            raise ZnalezionoWielePublikacjiInstytucjiV2Exception(objectId)

        return zapisz_publikacje_instytucji_v2(self, elem[0])

    def _delete_statements_with_retry(self, pbn_uid_id, max_tries=5):
        """Delete publication statements with retry on failure."""
        no_tries = max_tries
        while True:
            try:
                self.delete_all_publication_statements(pbn_uid_id)
                return True
            except CannotDeleteStatementsException as e:
                if no_tries < 0:
                    raise e
                no_tries -= 1
                time.sleep(0.5)

    def _handle_no_objectid(self, notificator, ret, js, pub):
        """Handle case when server doesn't return object ID."""
        msg = (
            f"UWAGA. Serwer PBN nie odpowiedział prawidłowym PBN UID dla"
            f" wysyłanego rekordu. Zgłoś sytuację do administratora serwisu. "
            f"{ret=}, {js=}, {pub=}"
        )
        if notificator is not None:
            notificator.error(msg)

        try:
            raise NoPBNUIDException(msg)
        except NoPBNUIDException:
            rollbar.report_exc_info(sys.exc_info())

        mail_admins("Serwer PBN nie zwrocil ID publikacji", msg, fail_silently=True)

    def _download_statements_with_retry(
        self, publication, objectId, notificator, max_tries=3
    ):
        """Download publication statements with retry on 500 errors."""
        no_tries = max_tries
        while True:
            try:
                self.download_statements_of_publication(publication)
                break
            except HttpException as e:
                if no_tries < 0 or e.status_code != 500:
                    raise e
                no_tries -= 1
                time.sleep(0.5)

        try:
            self.pobierz_publikacje_instytucji_v2(objectId=objectId)
        except PublikacjaInstytucjiV2NieZnalezionaException:
            notificator.warning(
                "Nie znaleziono oświadczeń dla publikacji po stronie PBN w wersji V2 API. Ten komunikat nie jest "
                "błędem. "
            )

    def _get_username_from_notificator(self, notificator):
        """Extract username from notificator if available."""
        if (
            notificator is not None
            and hasattr(notificator, "request")
            and hasattr(notificator.request, "user")
        ):
            return notificator.request.user.username
        return None

    def _handle_uid_change(self, pub, objectId, notificator, js, ret):
        """Handle case when publication UID changes."""
        if notificator is not None:
            notificator.error(
                f"UWAGA UWAGA UWAGA. Wg danych z PBN zmodyfikowano PBN UID tego rekordu "
                f"z wartości {pub.pbn_uid_id} na {objectId}. Technicznie nie jest to błąd, "
                f"ale w praktyce dobrze by było zweryfikować co się zadziało, zarówno po stronie"
                f"PBNu jak i BPP. Być może operujesz na rekordzie ze zdublowanym DOI/stronie WWW."
            )

        message = (
            f"Zarejestrowano zmianę ZAPISANEGO WCZEŚNIEJ PBN UID publikacji przez PBN, \n"
            f"Publikacja:\n{pub}\n\n"
            f"z UIDu {pub.pbn_uid_id} na {objectId}"
        )

        try:
            raise PBNUIDChangedException(message)
        except PBNUIDChangedException:
            rollbar.report_exc_info(sys.exc_info())

        mail_admins(
            "Zmiana PBN UID publikacji przez serwer PBN", message, fail_silently=True
        )

        PBNOdpowiedziNiepozadane.objects.create(
            rekord=pub,
            dane_wyslane=js,
            odpowiedz_serwera=ret,
            rodzaj_zdarzenia=PBNOdpowiedziNiepozadane.ZMIANA_UID,
            uzytkownik=self._get_username_from_notificator(notificator),
            stary_uid=pub.pbn_uid_id,
            nowy_uid=objectId,
        )

    def _handle_uid_conflict(self, pub, objectId, notificator, js, ret):
        """Handle case when new publication gets an existing UID."""
        from bpp.models import Rekord

        istniejace_rekordy = Rekord.objects.filter(pbn_uid_id=objectId)
        if notificator is not None:
            notificator.error(
                f'UWAGA UWAGA UWAGA. Wysłany rekord "{pub}" dostał w odpowiedzi z serwera PBN numer UID '
                f"rekordu JUŻ ISTNIEJĄCEGO W BAZIE DANYCH BPP, a konkretnie {istniejace_rekordy.all()}. "
                f"Z przyczyn oczywistych NIE MOGĘ ustawić takiego PBN UID gdyż wówczas unikalność numerów PBN "
                f"UID byłaby naruszona. Zapewne też doszło do "
                f"NADPISANIA danych w/wym rekordu po stronie PBNu. Powinieneś/aś wycofać zmiany w PBNie "
                f"za pomocą GUI, zgłosić tą sytuację do administratora oraz zaprzestać prób wysyłki "
                f"tego rekordu do wyjaśnienia. "
            )

        message = (
            f"Zarejestrowano ustawienie nowo wysłanej pracy ISTNIEJĄCEGO JUŻ W BAZIE PBN UID\n"
            f"Publikacja:\n{pub}\n\n"
            f"UIDu {objectId}\n"
            f"Istniejąca praca/e: {istniejace_rekordy.all()}"
        )

        try:
            raise PBNUIDSetToExistentException(message)
        except PBNUIDSetToExistentException:
            rollbar.report_exc_info(sys.exc_info())

        mail_admins(
            "Ustawienie ISTNIEJĄCEGO JUŻ W BAZIE PBN UID publikacji przez serwer PBN",
            message,
            fail_silently=True,
        )

        PBNOdpowiedziNiepozadane.objects.create(
            rekord=pub,
            dane_wyslane=js,
            odpowiedz_serwera=ret,
            rodzaj_zdarzenia=PBNOdpowiedziNiepozadane.UID_JUZ_ISTNIEJE,
            uzytkownik=self._get_username_from_notificator(notificator),
            nowy_uid=objectId,
        )

    def sync_publication(
        self,
        pub,
        notificator=None,
        force_upload=False,
        delete_statements_before_upload=False,
        export_pk_zero=None,
        always_affiliate_to_uid=None,
    ):
        """
        @param delete_statements_before_upload: gdy True, kasuj oświadczenia publikacji przed wysłaniem (jeżeli posiada
        PBN UID)
        """
        pub = self.eventually_coerce_to_publication(pub)

        if (
            delete_statements_before_upload
            and hasattr(pub, "pbn_uid_id")
            and pub.pbn_uid_id is not None
        ):
            try:
                self._delete_statements_with_retry(pub.pbn_uid_id)
                force_upload = True
            except CannotDeleteStatementsException:
                pass

        objectId, ret, js, bez_oswiadczen = self.upload_publication(
            pub,
            force_upload=force_upload,
            export_pk_zero=export_pk_zero,
            always_affiliate_to_uid=always_affiliate_to_uid,
        )

        if bez_oswiadczen and notificator is not None:
            notificator.info(
                "Rekord nie posiada oświadczeń - wysłano wyłącznie do repozytorium PBN. "
            )

        if not objectId:
            self._handle_no_objectid(notificator, ret, js, pub)
            return

        publication = self.download_publication(objectId=objectId)

        if not bez_oswiadczen:
            self._download_statements_with_retry(publication, objectId, notificator)

        if pub.pbn_uid_id != objectId:
            if pub.pbn_uid_id is not None:
                self._handle_uid_change(pub, objectId, notificator, js, ret)

            from bpp.models import Rekord

            istniejace_rekordy = Rekord.objects.filter(pbn_uid_id=objectId)
            if pub.pbn_uid_id is None and istniejace_rekordy.exists():
                self._handle_uid_conflict(pub, objectId, notificator, js, ret)
                return

            pub.pbn_uid = publication
            pub.save()

        return publication

    def eventually_coerce_to_publication(self, pub: Model | str) -> Model:
        if type(pub) is str:
            # Ciag znaków w postaci wydawnictwo_zwarte:123 pozwoli na podawanie tego
            # parametru do wywołań z linii poleceń
            model, pk = pub.split(":")
            ctype = ContentType.objects.get(app_label="bpp", model=model)
            pub = ctype.model_class().objects.get(pk=pk)

        return pub

    def upload_publication_fee(self, pub: Model):
        pub = self.eventually_coerce_to_publication(pub)
        if pub.pbn_uid_id is None:
            raise NoPBNUIDException(
                f"PBN UID (czyli 'numer odpowiednika w PBN') dla rekordu '{pub}' jest pusty."
            )

        fee = OplataZaWydawnictwoPBNAdapter(pub).pbn_get_json()
        if not fee:
            raise NoFeeDataException(
                f"Brak danych o opłatach za publikację {pub.pbn_uid_id}"
            )

        return self.post_publication_fee(pub.pbn_uid_id, fee)

    def _get_command_function(self, cmd):
        """Get function to execute from command name."""
        try:
            return getattr(self, cmd[0])
        except AttributeError as e:
            if self._interactive:
                print(f"No such command: {cmd}")
                return None
            raise e

    def _extract_arguments(self, lst):
        """Extract positional and keyword arguments from command list."""
        args = ()
        kw = {}
        for elem in lst:
            if elem.find(":") >= 1:
                k, n = elem.split(":", 1)
                kw[k] = n
            else:
                args += (elem,)
        return args, kw

    def _print_non_interactive_result(self, res):
        """Print result in non-interactive mode."""
        import json

        print(json.dumps(res))

    def _print_interactive_result(self, res):
        """Print result in interactive mode."""
        if type(res) is dict:
            pprint(res)
        elif is_iterable(res):
            if self._interactive and hasattr(res, "total_elements"):
                print(
                    "Incoming data: no_elements=",
                    res.total_elements,
                    "no_pages=",
                    res.total_pages,
                )
                input("Press ENTER to continue> ")
            for elem in res:
                pprint(elem)

    def exec(self, cmd):
        fun = self._get_command_function(cmd)
        if fun is None:
            return

        args, kw = self._extract_arguments(cmd[1:])
        res = fun(*args, **kw)

        if not sys.stdout.isatty():
            self._print_non_interactive_result(res)
        else:
            self._print_interactive_result(res)

    @transaction.atomic
    def download_disciplines(self):
        """Zapisuje słownik dyscyplin z API PBN do lokalnej bazy"""

        for elem in self.get_disciplines():
            validityDateFrom = elem.get("validityDateFrom", None)
            validityDateTo = elem.get("validityDateTo", None)
            uuid = elem["uuid"]

            parent_group, created = DisciplineGroup.objects.update_or_create(
                uuid=uuid,
                defaults={
                    "validityDateFrom": validityDateFrom,
                    "validityDateTo": validityDateTo,
                },
            )

            for discipline in elem["disciplines"]:
                # print("XXX", discipline["uuid"])
                Discipline.objects.update_or_create(
                    parent_group=parent_group,
                    uuid=discipline["uuid"],
                    defaults=dict(
                        code=discipline["code"],
                        name=discipline["name"],
                        polonCode=discipline["polonCode"],
                        scientificFieldName=discipline["scientificFieldName"],
                    ),
                )

    @transaction.atomic
    def sync_disciplines(self):
        self.download_disciplines()
        try:
            cur_dg = DisciplineGroup.objects.get_current()
        except DisciplineGroup.DoesNotExist as e:
            raise ValueError(
                "Brak aktualnego słownika dyscyplin na serwerze. Pobierz aktualny słownik "
                "dyscyplin z PBN."
            ) from e

        from bpp.models import Dyscyplina_Naukowa

        for dyscyplina in Dyscyplina_Naukowa.objects.all():
            wpis_tlumacza = TlumaczDyscyplin.objects.get_or_create(
                dyscyplina_w_bpp=dyscyplina
            )[0]

            wpis_tlumacza.pbn_2024_now = matchuj_aktualna_dyscypline_pbn(
                dyscyplina.kod, dyscyplina.nazwa
            )
            # Domyślnie szuka dla lat 2018-2022
            wpis_tlumacza.pbn_2017_2021 = matchuj_nieaktualna_dyscypline_pbn(
                dyscyplina.kod, dyscyplina.nazwa, rok_min=2018, rok_max=2022
            )

            wpis_tlumacza.pbn_2022_2023 = matchuj_nieaktualna_dyscypline_pbn(
                dyscyplina.kod, dyscyplina.nazwa, rok_min=2023, rok_max=2024
            )

            wpis_tlumacza.save()

        for discipline in cur_dg.discipline_set.all():
            if discipline.name == "weterynaria":
                pass
            # Każda dyscyplina z aktualnego słownika powinna być wpisana do systemu BPP
            try:
                TlumaczDyscyplin.objects.get(pbn_2024_now=discipline)
            except TlumaczDyscyplin.DoesNotExist:
                try:
                    dyscyplina_w_bpp = Dyscyplina_Naukowa.objects.get(
                        kod=normalize_kod_dyscypliny(discipline.code)
                    )
                    TlumaczDyscyplin.objects.get_or_create(
                        dyscyplina_w_bpp=dyscyplina_w_bpp
                    )

                except Dyscyplina_Naukowa.DoesNotExist:
                    dyscyplina_w_bpp = Dyscyplina_Naukowa.objects.create(
                        kod=normalize_kod_dyscypliny(discipline.code),
                        nazwa=discipline.name,
                    )
                    TlumaczDyscyplin.objects.get_or_create(
                        dyscyplina_w_bpp=dyscyplina_w_bpp
                    )

    def interactive(self):
        self._interactive = True
        while True:
            cmd = input("cmd> ")
            if cmd == "exit":
                break
            self.exec(cmd.split(" "))
