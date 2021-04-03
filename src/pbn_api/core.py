import warnings
from json import JSONDecodeError
from urllib.parse import quote

import requests

from pbn_api.exceptions import (
    AccessDeniedException,
    HttpException,
    PraceSerwisoweException,
)

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


class OAuthMixin:
    def authorize(self):
        client_id = "zsun-implicit"
        redirect_uri = "https://pbn-micro-alpha.opi.org.pl/auth/oauth/redirector"
        authorization_base_url = (
            "https://pbn-micro-alpha.opi.org.pl/auth/oauth/authorize"
        )

        # >>> # OAuth endpoints given in the Google API documentation
        # >>> authorization_base_url = "https://accounts.google.com/o/oauth2/v2/auth"
        # >>> token_url = "https://www.googleapis.com/oauth2/v4/token"

        from requests_oauthlib import OAuth2Session

        pbn = OAuth2Session(client_id, redirect_uri=redirect_uri)

        # >>> # Redirect user to Google for authorization
        authorization_url, state = pbn.authorization_url(authorization_base_url)
        import webbrowser

        webbrowser.open(authorization_url)

        redirect_response = input("Paste the full redirect URL here:")
        access_token = redirect_response.split("#access_token=")[1].split("&")[0]
        print("ACCESS TOKEN", access_token)
        self.access_token = access_token

        # pbn.fetch_token(token_url,  client_secret=client_secret,
        #  authorization_response=redirect_response)


class RequestsTransport(OAuthMixin, PBNClientTransport):
    def get(self, url, headers=None):
        sent_headers = {"X-App-Id": self.app_id, "X-App-Token": self.app_token}

        if hasattr(self, "access_token"):
            sent_headers["X-User-Token"] = self.access_token

        if headers is not None:
            sent_headers.update(headers)
        ret = requests.get(self.base_url + url, headers=sent_headers)

        if ret.status_code == 403:
            # Needs auth
            if ret.json()["message"] == "Access Denied":
                # Autoryzacja użytkownika jest poprawna, jednakże nie ma on po stronie PBN
                # takiego uprawnienia...
                raise AccessDeniedException(url)

            # elif ret.json['message'] == "Forbidden":  # <== to dostaniemy, gdy token zły lub brak

            if hasattr(self, "authorize"):
                self.authorize()
                return self.get(url, headers)

        if ret.status_code >= 400:
            raise HttpException(ret.status_code, ret.content)

        try:
            return ret.json()
        except JSONDecodeError as e:
            if ret.status_code == 200 and b"prace serwisowe" in ret.content:
                # open("pbn_client_dump.html", "wb").write(ret.content)
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


class InstitutionsMixin:
    def get_institutions(self):
        return self.transport.get_pages("/v1/institutions/page")

    def get_institution_by_id(self, id):
        return self.transport.get_pages(f"/v1/institutions/{id}")

    def get_institution_by_version(self, version):
        return self.transport.get_pages(f"/v1/institutions/version/{version}")

    def get_institution_metadata(self, id):
        return self.transport.get_pages(f"/v1/institutions/{id}/metadata")

    def get_institutions_polon(self):
        return self.transport.get_pages("/v1/institutions/polon/page")

    def get_institutions_polon_by_uid(self, uid):
        return self.transport.get(f"/v1/institutions/polon/uid/{uid}")

    def get_institutions_polon_by_id(self, id):
        return self.transport.get(f"/v1/institutions/polon/{id}")


class InstitutionsProfileMixin:
    # XXX: wymaga autoryzacji
    def get_institution_publications(self):
        return self.transport.get_pages("/v1/institutionProfile/publications/page")

    def get_institution_statements(self):
        return self.transport.get_pages(
            "/v1/institutionProfile/publications/page/statements"
        )


class JournalsMixin:
    def get_journals_mnisw(self):
        return self.transport.get_pages("/v1/journals/mnisw/page")

    def get_journals(self):
        return self.transport.get_pages("/v1/journals/page")

    def get_journal_by_version(self, version):
        return self.transport.get(f"/v1/journals/version/{version}")

    def get_journal_by_id(self, id):
        return self.transport.get(f"/v1/journals/{id}")

    def get_journal_metadata(self, id):
        return self.transport.get(f"/v1/journals/{id}/metadata")


class PersonMixin:
    def get_people_by_institution_id(self, id):
        return self.transport.get(f"/v1/person/institution/{id}")

    def get_person_by_natural_id(self, id):
        return self.transport.get(f"/v1/person/natural/{id}")

    def get_person_by_orcid(self, orcid):
        return self.transport.get(f"/v1/person/orcid/{orcid}")

    def get_people(self):
        return self.transport.get_pages("/v1/person/page")

    def get_person_by_polon_uid(self, uid):
        return self.transport.get(f"/v1/person/polon/{uid}")

    def get_person_by_version(self, version):
        return self.transport.get(f"/v1/person/version/{version}")

    def get_person_by_id(self, id):
        return self.transport.get(f"/v1/person/{id}")


class PublishersMixin:
    def get_publishers_mnisw(self):
        return self.transport.get_pages("/v1/publishers/mnisw/page")

    def get_publishers_mnisw_yearlist(self):
        return self.transport.get_pages("/v1/publishers/mnisw/page/yearlist")

    def get_publishers(self):
        return self.transport.get_pages("/v1/publishers/page")

    def get_publisher_by_version(self, version):
        return self.transport.get(f"/v1/publishers/version/{version}")

    def get_publisher_by_id(self, id):
        return self.transport.get(f"/v1/publishers/{id}")

    def get_publisher_metadata(self, id):
        return self.transport.get(f"/v1/publishers/{id}/metadata")


class PublicationsMixin:
    def get_publication_by_doi(self, doi):
        return self.transport.get(
            f"/v1/publications/doi/?doi={quote(doi, safe='')}",
        )

    def get_publication_by_doi_page(self, doi):
        return self.transport.get_pages(
            f"/v1/publications/doi/page?doi={quote(doi, safe='')}", headers={"doi": doi}
        )

    def get_publication_by_id(self, id):
        return self.transport.get(f"/v1/publications/id/{id}")

    def get_publication_metadata(self, id):
        return self.transport.get(f"/v1/publications/id/{id}/metadata")

    def get_publications(self):
        return self.transport.get_pages("/v1/publications/page")

    def get_publication_by_version(self, version):
        return self.transport.get(f"/v1/publications/version/{version}")


class PBNClient(
    ConferencesMixin,
    DictionariesMixin,
    InstitutionsMixin,
    InstitutionsProfileMixin,
    JournalsMixin,
    PersonMixin,
    PublicationsMixin,
    PublishersMixin,
):
    def __init__(self, transport):
        self.transport = transport
