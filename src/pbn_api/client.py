import random
import sys
import time
import warnings
from builtins import NotImplementedError
from pprint import pprint
from urllib.parse import parse_qs, quote, urlparse

import requests
from django.db import transaction
from django.db.models import Model
from requests import ConnectionError
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
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_GET_JOURNAL_BY_ID,
    PBN_GET_LANGUAGES_URL,
    PBN_GET_PUBLICATION_BY_ID_URL,
    PBN_POST_PUBLICATION_FEE_URL,
    PBN_POST_PUBLICATIONS_URL,
    PBN_SEARCH_PUBLICATIONS_URL,
)
from pbn_api.exceptions import (
    AccessDeniedException,
    AuthenticationResponseError,
    HttpException,
    NeedsPBNAuthorisationException,
    NoFeeDataException,
    NoPBNUIDException,
    PraceSerwisoweException,
    SameDataUploadedRecently,
)
from pbn_api.models import TlumaczDyscyplin
from pbn_api.models.discipline import Discipline, DisciplineGroup
from pbn_api.models.sentdata import SentData

from django.contrib.contenttypes.models import ContentType

from django.utils.itercompat import is_iterable


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
    def get(self, url, headers=None, fail_on_auth_missing=False):
        sent_headers = {"X-App-Id": self.app_id, "X-App-Token": self.app_token}
        if self.access_token:
            sent_headers["X-User-Token"] = self.access_token

        # Jeżeli ustawimy taki nagłówek dla "niewinnych" zapytań GET, to PBN
        # API odrzuca takie połączenie z kodem 403, stąd nie:
        # if hasattr(self, "access_token"):
        #     sent_headers["X-User-Token"] = self.access_token

        if headers is not None:
            sent_headers.update(headers)

        retries = 0
        MAX_RETRIES = 15

        while retries < MAX_RETRIES:
            try:
                ret = requests.get(self.base_url + url, headers=sent_headers)
                break
            except (SSLError, ConnectionError) as e:
                retries += 1
                time.sleep(random.randint(1, 5))
                if retries >= MAX_RETRIES:
                    raise e

        if ret.status_code == 403:
            if fail_on_auth_missing:
                raise AccessDeniedException(url, smart_content(ret.content))
            # Needs auth
            if ret.json()["message"] == "Access Denied":
                # Autoryzacja użytkownika jest poprawna, jednakże nie ma on po stronie PBN
                # takiego uprawnienia...
                raise AccessDeniedException(url, smart_content(ret.content))

            # elif ret.json['message'] == "Forbidden":  # <== to dostaniemy, gdy token zły lub brak

            if hasattr(self, "authorize"):
                ret = self.authorize(self.base_url, self.app_id, self.app_token)
                if not ret:
                    return

                # Podejmuj ponowną próbę tylko w przypadku udanej autoryzacji
                return self.get(url, headers, fail_on_auth_missing=True)

        if ret.status_code >= 400:
            raise HttpException(ret.status_code, url, smart_content(ret.content))

        try:
            return ret.json()
        except JSONDecodeError as e:
            if ret.status_code == 200 and b"prace serwisowe" in ret.content:
                # open("pbn_client_dump.html", "wb").write(ret.content)
                raise PraceSerwisoweException()
            raise e

    def post(self, url, headers=None, body=None, delete=False):
        if not hasattr(self, "access_token"):
            ret = self.authorize(self.base_url, self.app_id, self.app_token)
            if not ret:
                return
            return self.post(url, headers=headers, body=body, delete=delete)

        sent_headers = {
            "X-App-Id": self.app_id,
            "X-App-Token": self.app_token,
            "X-User-Token": self.access_token,
        }

        if headers is not None:
            sent_headers.update(headers)

        method = requests.post
        if delete:
            method = requests.delete

        ret = method(self.base_url + url, headers=sent_headers, json=body)
        if ret.status_code == 403:
            try:
                ret_json = ret.json()
            except BaseException:
                raise HttpException(
                    ret.status_code,
                    url,
                    "Blad podczas odkodowywania JSON podczas odpowiedzi 403: "
                    + smart_content(ret.content),
                )

            # Needs auth
            if ret_json.get("message") == "Access Denied":
                # Autoryzacja użytkownika jest poprawna, jednakże nie ma on po stronie PBN
                # takiego uprawnienia...
                raise AccessDeniedException(url, smart_content(ret.content))

            if ret_json.get("message") == "Forbidden" and ret_json.get(
                "description"
            ).startswith(NEEDS_PBN_AUTH_MSG):
                # (403, '/api/v1/search/publications?size=10', '{"code":403,"message":"Forbidden",
                # "description":"W celu poprawnej autentykacji należy podać poprawny token użytkownika aplikacji. Podany
                # token użytkownika ... w ramach aplikacji ... nie istnieje lub został
                # unieważniony!"}')
                raise NeedsPBNAuthorisationException(
                    ret.status_code, url, smart_content(ret.content)
                )

            # mpasternak, 5.09.2021: nie do końca jestem pewny, czy kod wywołujący self.authorize (nast. 2 linijki)
            # zostawić w tej sytuacji. Tak było 'historycznie', ale widzę też, że po wywołaniu self.authorize
            # ta funkcja zawsze wykonywała "if ret.status_code >= 403" i zwracała Exception. Teoretycznie
            # to chyba zostało tutaj z powodu klienta command-line, który to na ten moment priorytetem
            # przecież nie jest.
            if hasattr(self, "authorize"):
                self.authorize(self.base_url, self.app_id, self.app_token)
                # self.authorize()

        #
        # mpasternak 7.09.2021, poniżej "przymiarki" do analizowania zwróconych błędów z PBN
        #
        # if ret.status_code == 400:
        #     try:
        #         ret_json = ret.json()
        #     except BaseException:
        #         raise HttpException(
        #             ret.status_code,
        #             url,
        #             "Blad podczas odkodowywania JSON podczas odpowiedzi 400: "
        #             + smart_content(ret.content),
        #         )
        #     if ret_json.get("message") == "Bad Request" and ret_json.get("description") == "Validation failed."
        #     and ret_json.get("details")
        #
        #     HttpException(400, '/api/v1/publications',
        #                   '{"code":400,"message":"Bad Request","description":"Validation failed.",
        #                   "details":{"doi":"DOI jest błędny lub nie udało się pobrać informacji z serwisu DOI!"}}')

        if ret.status_code >= 400:
            raise HttpException(ret.status_code, url, smart_content(ret.content))

        try:
            return ret.json()
        except JSONDecodeError as e:
            if ret.status_code == 200:
                if ret.content == b"":
                    return

                if b"prace serwisowe" in ret.content:
                    # open("pbn_client_dump.html", "wb").write(ret.content)
                    raise PraceSerwisoweException()

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
            )
            return res
        return PageableResource(
            self, res, url=url, headers=headers, body=body, method=method
        )

    def get_pages(self, url, headers=None, page_size=10, *args, **kw):
        return self._pages(
            "get", url=url, headers=headers, page_size=page_size, *args, **kw
        )

    def post_pages(self, url, headers=None, body=None, page_size=10, *args, **kw):
        # Jak get_pages, ale methoda to post
        if body is None:
            body = kw

        return self._pages(
            "post",
            url=url,
            headers=headers,
            body=body,
            page_size=page_size,
            *args,
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
    def get_institution_publications(self, page_size=10):
        return self.transport.get_pages(
            "/api/v1/institutionProfile/publications/page", page_size=page_size
        )

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

    def delete_all_publication_statements(self, publicationId):
        return self.transport.delete(
            PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=publicationId),
            body={"all": True, "statementsOfPersons": []},
        )

    def delete_publication_statement(self, publicationId, personId, role):
        return self.transport.delete(
            PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=publicationId),
            body={"statementsOfPersons": [{"personId": personId, "role": role}]},
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


class AuthorMixin:
    def get_author_by_id(self, id):
        return self.transport.get(f"/api/v1/author/{id}")


class SearchMixin:
    def search_publications(self, *args, **kw):
        return self.transport.post_pages(PBN_SEARCH_PUBLICATIONS_URL, body=kw)


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
    SearchMixin,
):
    _interactive = False

    def __init__(self, transport: RequestsTransport):
        self.transport = transport

    def post_publication(self, json):
        return self.transport.post(PBN_POST_PUBLICATIONS_URL, body=json)

    def post_publication_fee(self, publicationId, json):
        return self.transport.post(
            PBN_POST_PUBLICATION_FEE_URL.format(id=publicationId), body=json
        )

    def upload_publication(
        self, rec, force_upload=False, export_pk_zero=None, always_affiliate_to_uid=None
    ):
        js = WydawnictwoPBNAdapter(
            rec,
            export_pk_zero=export_pk_zero,
            always_affiliate_to_uid=always_affiliate_to_uid,
        ).pbn_get_json()
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

        return ret, js

    def download_publication(self, doi=None, objectId=None):
        from .integrator import zapisz_mongodb
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
        from .integrator import pobierz_mongodb, zapisz_oswiadczenie_instytucji

        OswiadczenieInstytucji.objects.filter(publicationId_id=pub.pk).delete()

        pobierz_mongodb(
            self.get_institution_statements_of_single_publication(pub.pk, 5120),
            None,
            fun=zapisz_oswiadczenie_instytucji,
            client=self,
            disable_progress_bar=True,
        )

    def sync_publication(
        self,
        pub,
        force_upload=False,
        delete_statements_before_upload=False,
        export_pk_zero=None,
        always_affiliate_to_uid=None,
    ):
        """
        @param delete_statements_before_upload: gdy True, kasuj oświadczenia publikacji przed wysłaniem (jeżeli posiada
        PBN UID)
        """

        # if not pub.doi:
        #     raise WillNotExportError("Ustaw DOI dla publikacji")

        pub = self.eventually_coerce_to_publication(pub)

        #
        if (
            delete_statements_before_upload
            and hasattr(pub, "pbn_uid_id")
            and pub.pbn_uid_id is not None
        ):
            try:
                self.delete_all_publication_statements(pub.pbn_uid_id)

                # Jeżeli zostały skasowane dane, to wymuś wysłanie rekordu, niezależnie
                # od stanu tabeli SentData
                force_upload = True
            except HttpException as e:
                NIE_ISTNIEJA = "Nie istnieją oświadczenia dla publikacji"

                ignored_exception = False

                if e.status_code == 400:
                    if e.json:
                        try:
                            try:
                                msg = e.json["details"]["publicationId"]
                            except KeyError:
                                msg = e.json["details"][
                                    f"publicationId.{pub.pbn_uid_id}"
                                ]
                            if NIE_ISTNIEJA in msg:
                                ignored_exception = True
                        except (TypeError, KeyError):
                            if NIE_ISTNIEJA in e.content:
                                ignored_exception = True

                    else:
                        if NIE_ISTNIEJA in e.content:
                            ignored_exception = True

                if not ignored_exception:
                    raise e

        # Wgraj dane do PBN
        ret, js = self.upload_publication(
            pub,
            force_upload=force_upload,
            export_pk_zero=export_pk_zero,
            always_affiliate_to_uid=always_affiliate_to_uid,
        )

        # Pobierz zwrotnie dane z PBN
        publication = self.download_publication(objectId=ret["objectId"])
        self.download_statements_of_publication(publication)

        # Utwórz obiekt zapisanych danych. Dopiero w tym miejscu, bo jeżeli zostanie
        # utworzony nowy rekord po stronie PBN, to pbn_uid_id musi wskazywać na
        # bazę w tabeli Publication, która została chwile temu pobrana...
        SentData.objects.updated(pub, js, pbn_uid_id=ret["objectId"])

        if pub.pbn_uid_id != ret["objectId"]:
            pub.pbn_uid = publication
            pub.save()

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

        def extract_arguments(lst):
            args = ()
            kw = {}
            for elem in lst:
                if elem.find(":") >= 1:
                    k, n = elem.split(":", 1)
                    kw[k] = n
                else:
                    args += (elem,)

            return args, kw

        args, kw = extract_arguments(cmd[1:])
        res = fun(*args, **kw)

        if not sys.stdout.isatty():
            # Non-interactive mode, just output the json
            import json

            print(json.dumps(res))
        else:
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
        except DisciplineGroup.DoesNotExist:
            raise ValueError(
                "Brak aktualnego słownika dyscyplin na serwerze. Pobierz aktualny słownik "
                "dyscyplin z PBN."
            )

        from bpp.models import Dyscyplina_Naukowa

        for dyscyplina in Dyscyplina_Naukowa.objects.all():
            wpis_tlumacza = TlumaczDyscyplin.objects.get_or_create(
                dyscyplina_w_bpp=dyscyplina
            )[0]

            wpis_tlumacza.pbn_2022_now = matchuj_aktualna_dyscypline_pbn(
                dyscyplina.kod, dyscyplina.nazwa
            )
            # Domyślnie szuka dla lat 2017-2022
            wpis_tlumacza.pbn_2017_2021 = matchuj_nieaktualna_dyscypline_pbn(
                dyscyplina.kod, dyscyplina.nazwa
            )

            wpis_tlumacza.save()

        for discipline in cur_dg.discipline_set.all():
            # Każda dyscyplina z aktualnego słownika powinna być wpisana do systemu BPP
            try:
                TlumaczDyscyplin.objects.get(pbn_2022_now=discipline)
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
