"""Publication synchronization mixin for PBN API client."""

import sys
import time

import rollbar
from django.contrib.contenttypes.models import ContentType
from django.core.mail import mail_admins
from django.db import transaction
from django.db.models import Model

from pbn_api.adapters.wydawnictwo import (
    OplataZaWydawnictwoPBNAdapter,
    WydawnictwoPBNAdapter,
)
from pbn_api.const import (
    PBN_POST_PUBLICATION_FEE_URL,
    PBN_POST_PUBLICATION_NO_STATEMENTS_URL,
    PBN_POST_PUBLICATIONS_URL,
)
from pbn_api.exceptions import (
    CannotDeleteStatementsException,
    HttpException,
    NoFeeDataException,
    NoPBNUIDException,
    PBNUIDChangedException,
    PBNUIDSetToExistentException,
    PublikacjaInstytucjiV2NieZnalezionaException,
    SameDataUploadedRecently,
    ZnalezionoWielePublikacjiInstytucjiV2Exception,
)
from pbn_api.models.pbn_odpowiedzi_niepozadane import PBNOdpowiedziNiepozadane
from pbn_api.models.sentdata import SentData
from pbn_api.utils import rename_dict_key


class PublicationSyncMixin:
    """Mixin providing publication synchronization methods."""

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
                    "Lista zwróconych obiektów przy wysyłce pracy bez oświadczeń "
                    "różna od jednego. "
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
        w JSONie (klucz: "statements") używa albo api /v1/ do wysyłki publikacji
        "ze wszystkim", albo korzysta z api /v1/ repozytorialnego.

        Zwracane wyniki wyjściowe też różnią się w zależnosci od użytego API stąd też
        ta funkcja stara się w miarę rozsądnie to ogarnąć.
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
                SentData.objects.mark_as_successful(rec, api_response_status=str(ret))
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
        from pbn_api.models import Publication
        from pbn_integrator.utils import zapisz_mongodb

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
                "Nie znaleziono oświadczeń dla publikacji po stronie PBN w wersji "
                "V2 API. Ten komunikat nie jest błędem. "
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
                f"z wartości {pub.pbn_uid_id} na {objectId}. Technicznie nie jest to "
                f"błąd, ale w praktyce dobrze by było zweryfikować co się zadziało, "
                f"zarówno po stronie PBNu jak i BPP. Być może operujesz na rekordzie "
                f"ze zdublowanym DOI/stronie WWW."
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
                f'UWAGA UWAGA UWAGA. Wysłany rekord "{pub}" dostał w odpowiedzi '
                f"z serwera PBN numer UID "
                f"rekordu JUŻ ISTNIEJĄCEGO W BAZIE DANYCH BPP, a konkretnie "
                f"{istniejace_rekordy.all()}. "
                f"Z przyczyn oczywistych NIE MOGĘ ustawić takiego PBN UID gdyż wówczas "
                f"unikalność numerów PBN "
                f"UID byłaby naruszona. Zapewne też doszło do "
                f"NADPISANIA danych w/wym rekordu po stronie PBNu. Powinieneś/aś "
                f"wycofać zmiany w PBNie "
                f"za pomocą GUI, zgłosić tą sytuację do administratora oraz zaprzestać "
                f"prób wysyłki "
                f"tego rekordu do wyjaśnienia. "
            )

        message = (
            f"Zarejestrowano ustawienie nowo wysłanej pracy ISTNIEJĄCEGO JUŻ W BAZIE "
            f"PBN UID\n"
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

    def sync_publication(  # noqa: C901
        self,
        pub,
        notificator=None,
        force_upload=False,
        delete_statements_before_upload=False,
        export_pk_zero=None,
        always_affiliate_to_uid=None,
    ):
        """
        @param delete_statements_before_upload: gdy True, kasuj oświadczenia publikacji
            przed wysłaniem (jeżeli posiada PBN UID)
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
                "Rekord nie posiada oświadczeń - wysłano wyłącznie do repozytorium PBN."
            )

        if not objectId:
            self._handle_no_objectid(notificator, ret, js, pub)
            return

        publication = self.download_publication(objectId=objectId)

        # Update SentData with the publication link now that it exists in the database
        try:
            sent_data = SentData.objects.get_for_rec(pub)
            if sent_data.pbn_uid_id is None:
                sent_data.pbn_uid_id = publication.pk
                sent_data.save()
        except SentData.DoesNotExist:
            # This shouldn't happen if upload_publication was called,
            # but handle gracefully
            pass

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
                f"PBN UID (czyli 'numer odpowiednika w PBN') dla rekordu '{pub}' "
                f"jest pusty."
            )

        fee = OplataZaWydawnictwoPBNAdapter(pub).pbn_get_json()
        if not fee:
            raise NoFeeDataException(
                f"Brak danych o opłatach za publikację {pub.pbn_uid_id}"
            )

        return self.post_publication_fee(pub.pbn_uid_id, fee)
