import warnings
from json import JSONDecodeError
from pprint import pprint
from urllib.parse import parse_qs, quote, urlparse

import requests

from pbn_api.exceptions import (
    AccessDeniedException,
    AuthenticationResponseError,
    HttpException,
    PraceSerwisoweException,
    SameDataUploadedRecently,
)
from pbn_api.models import SentData

from django.utils.itercompat import is_iterable

DEFAULT_BASE_URL = "https://pbn-micro-alpha.opi.org.pl"


class PBNClientTransport:
    def __init__(self, app_id, app_token, base_url, user_token=None):
        self.app_id = app_id
        self.app_token = app_token

        self.base_url = base_url
        if self.base_url is None:
            self.base_url = DEFAULT_BASE_URL

        self.access_token = user_token


class PageableResource:
    def __init__(self, transport, res, url, headers):
        self.url = url
        self.headers = headers
        self.transport = transport

        try:
            self.current_content = res["content"]
        except KeyError:
            self.current_content = []
        self.current_page = res["number"]
        self.total_elements = res["totalElements"]
        self.total_pages = res["totalPages"]
        self.done = False

    def count(self):
        return self.total_elements

    def fetch_next_page(self):
        self.current_page += 1
        if self.current_page > self.total_pages:
            return
        res = self.transport.get(
            self.url + f"&page={self.current_page}", headers=self.headers
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
    @classmethod
    def get_auth_url(klass, base_url, app_id):
        return f"{base_url}/auth/pbn/api/registration/user/token/{app_id}"

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
        except ValueError:
            raise AuthenticationResponseError(response.content)

        return response.json().get("X-User-Token")

    def authorize(self, base_url, app_id, app_token):
        from pbn_api.conf import settings

        if self.access_token:
            return True

        self.access_token = getattr(settings, "PBN_CLIENT_USER_TOKEN")
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
    def get(self, url, headers=None):
        sent_headers = {"X-App-Id": self.app_id, "X-App-Token": self.app_token}

        # Jeżeli ustawimy taki nagłówek dla "niewinnych" zapytań GET, to PBN
        # API odrzuca takie połączenie z kodem 403, stąd nie:
        # if hasattr(self, "access_token"):
        #     sent_headers["X-User-Token"] = self.access_token

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
                ret = self.authorize(self.base_url, self.app_id, self.app_token)
                if not ret:
                    return

                # Podejmuj ponowną próbę tylko w przypadku udanej autoryzacji
                return self.get(url, headers)

        if ret.status_code >= 400:
            raise HttpException(ret.status_code, url, ret.content)

        try:
            return ret.json()
        except JSONDecodeError as e:
            if ret.status_code == 200 and b"prace serwisowe" in ret.content:
                # open("pbn_client_dump.html", "wb").write(ret.content)
                raise PraceSerwisoweException()
            raise e

    def post(self, url, headers=None, body=None):
        if not hasattr(self, "access_token"):
            ret = self.authorize(self.base_url, self.app_id, self.app_token)
            if not ret:
                return
            return self.post(url, headers=headers, body=body)

        sent_headers = {
            "X-App-Id": self.app_id,
            "X-App-Token": self.app_token,
            "X-User-Token": self.access_token,
        }

        if headers is not None:
            sent_headers.update(headers)

        ret = requests.post(self.base_url + url, headers=sent_headers, json=body)
        if ret.status_code == 403:
            # Needs auth
            if ret.json()["message"] == "Access Denied":
                # Autoryzacja użytkownika jest poprawna, jednakże nie ma on po stronie PBN
                # takiego uprawnienia...
                raise AccessDeniedException(url)

            # elif ret.json['message'] == "Forbidden":  # <== to dostaniemy, gdy token zły lub brak

            if hasattr(self, "authorize"):
                self.authorize(self.base_url, self.app_id, self.app_token)
                # self.authorize()

        if ret.status_code >= 400:
            raise HttpException(ret.status_code, url, ret.content)

        try:
            return ret.json()
        except JSONDecodeError as e:
            if ret.status_code == 200 and b"prace serwisowe" in ret.content:
                # open("pbn_client_dump.html", "wb").write(ret.content)
                raise PraceSerwisoweException()
            raise e

    def get_pages(self, url, headers=None, page_size=10, *args, **kw):
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
        return self.transport.get("/api/v1/dictionary/disciplines")

    def get_languages(self):
        return self.transport.get("/api/v1/dictionary/languages")


class InstitutionsMixin:
    def get_institutions(self, *args, **kw):
        return self.transport.get_pages("/api/v1/institutions/page", *args, **kw)

    def get_institution_by_id(self, id):
        return self.transport.get_pages(f"/api/v1/institutions/{id}")

    def get_institution_by_version(self, version):
        return self.transport.get_pages(f"/api/v1/institutions/version/{version}")

    def get_institution_metadata(self, id):
        return self.transport.get_pages(f"/api/v1/institutions/{id}/metadata")

    def get_institutions_polon(self):
        return self.transport.get_pages("/api/v1/institutions/polon/page")

    def get_institutions_polon_by_uid(self, uid):
        return self.transport.get(f"/api/v1/institutions/polon/uid/{uid}")

    def get_institutions_polon_by_id(self, id):
        return self.transport.get(f"/api/v1/institutions/polon/{id}")


class InstitutionsProfileMixin:
    # XXX: wymaga autoryzacji
    def get_institution_publications(self):
        return self.transport.get_pages("/api/v1/institutionProfile/publications/page")

    def get_institution_statements(self):
        return self.transport.get_pages(
            "/api/v1/institutionProfile/publications/page/statements"
        )


class JournalsMixin:
    def get_journals_mnisw(self, *args, **kw):
        return self.transport.get_pages("/api/v1/journals/mnisw/page", *args, **kw)

    def get_journals(self, *args, **kw):
        return self.transport.get_pages("/api/v1/journals/page", *args, **kw)

    def get_journal_by_version(self, version):
        return self.transport.get(f"/api/v1/journals/version/{version}")

    def get_journal_by_id(self, id):
        return self.transport.get(f"/api/v1/journals/{id}")

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
        return self.transport.get(f"/api/v1/publications/id/{id}")

    def get_publication_metadata(self, id):
        return self.transport.get(f"/api/v1/publications/id/{id}/metadata")

    def get_publications(self, **kw):
        return self.transport.get_pages("/api/v1/publications/page", **kw)

    def get_publication_by_version(self, version):
        return self.transport.get(f"/api/v1/publications/version/{version}")


class AuthorMixin:
    def get_author_by_id(self, id):
        return self.transport.get(f"/api/v1/author/{id}")


class PBNClient(
    AuthorMixin,
    ConferencesMixin,
    DictionariesMixin,
    InstitutionsMixin,
    InstitutionsProfileMixin,
    JournalsMixin,
    PersonMixin,
    PublicationsMixin,
    PublishersMixin,
):
    _interactive = False

    def __init__(self, transport: RequestsTransport):
        self.transport = transport

    def post_publication(self, json):
        return self.transport.post("/api/v1/publications", body=json)

    def upload_publication(self, rec, force_upload=False):
        js = rec.pbn_get_json()
        if not force_upload:
            needed = SentData.objects.check_if_needed(rec, js)
            if not needed:
                raise SameDataUploadedRecently(
                    SentData.objects.get_for_rec(rec).last_updated_on
                )
        try:
            ret = self.post_publication(js)
        except Exception as e:
            SentData.objects.updated(rec, js, uploaded_okay=False, exception=str(e))
            raise e

        SentData.objects.updated(rec, js)
        return ret

    def download_publication(self, doi=None, objectId=None):
        from .integrator import zapisz_mongodb
        from .models import Publication

        assert doi or objectId

        if doi:
            data = self.get_publication_by_doi(doi)
        elif objectId:
            data = self.get_publication_by_id(objectId)

        return zapisz_mongodb(data, Publication)

    def sync_publication(self, pub, force_upload=False):
        # if not pub.doi:
        #     raise WillNotExportError("Ustaw DOI dla publikacji")

        ret = self.upload_publication(pub, force_upload=force_upload)

        publication = self.download_publication(objectId=ret["objectId"])
        if pub.pbn_uid_id != ret["objectId"]:
            pub.pbn_uid = publication
            pub.save()

    def demo(self):
        from bpp.models import Wydawnictwo_Ciagle

        pub = Wydawnictwo_Ciagle.objects.filter(rok=2020).exclude(doi=None).first()
        self.sync_publication(pub, force_upload=True)

    def exec(self, cmd):
        try:
            fun = getattr(self, cmd[0])
        except AttributeError as e:
            if self._interactive:
                print("No such command: %s" % cmd)
                return
            else:
                raise e

        res = fun(*cmd[1:])
        if type(res) == dict:
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

    def interactive(self):
        self._interactive = True
        while True:
            cmd = input("cmd> ")
            if cmd == "exit":
                break
            self.exec(cmd.split(" "))
