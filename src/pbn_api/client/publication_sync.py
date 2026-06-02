"""Publication synchronization mixin for PBN API client."""

import logging
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
    PBN_POST_PUBLICATION_NO_STATEMENTS_URL,
    PBN_POST_PUBLICATIONS_URL,
)
from pbn_api.exceptions import (
    CannotDeleteStatementsException,
    DaneLokalneWymagajaAktualizacjiException,
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
from pbn_client.statements import StatementsMixin

logger = logging.getLogger(__name__)


class PublicationSyncMixin(StatementsMixin):
    """Orchestracja synchronizacji publikacji BPP↔PBN (warstwa BPP-aware).

    Czyste operacje protokołu (POST/GET, diff/DELETE oświadczeń) dziedziczy
    z ``pbn_client.statements.StatementsMixin``; tutaj zostaje logika znająca
    rekord BPP, ``Uczelnia`` i modele persystencji.
    """

    def _prepare_publication_json(self, rec, export_pk_zero, always_affiliate_to_uid):
        """Przygotowuje JSON publikacji do wysyłki.

        Decyzja o endpoincie wynika z obecności klucza ``statements`` w
        payloadzie z adaptera:

        - Praca ma lokalne statements → zwracamy surowy JSON adaptera,
          ``upload_publication`` POST-uje do ``/api/v1/publications``
          (all-in-one).
        - Praca nie ma lokalnych statements (uczelnia z flagą
          ``pbn_wysylaj_bez_oswiadczen=True``) → konwertujemy przez
          ``convert_json_with_statements_to_no_statements`` (renames pól
          + brak ``fee``); ``upload_publication`` POST-uje do
          ``/api/v1/repositorium/publications``.

        Adapter rzuca ``StatementsMissing`` gdy brak statements + flaga
        uczelni ``=False`` — ten przypadek nie dochodzi tu.

        Zwraca: ``(js, bez_oswiadczen)``.
        """
        js = WydawnictwoPBNAdapter(
            rec,
            uczelnia=self.uczelnia,
            export_pk_zero=export_pk_zero,
            always_affiliate_to_uid=always_affiliate_to_uid,
        ).pbn_get_json()

        bez_oswiadczen = "statements" not in js
        if bez_oswiadczen:
            js = self.convert_json_with_statements_to_no_statements(js)

        return js, bez_oswiadczen

    def _check_upload_needed(self, rec, js, force_upload):
        """Check if upload is needed."""
        if not force_upload:
            needed = SentData.objects.check_if_upload_needed(rec, js)
            if not needed:
                raise SameDataUploadedRecently(
                    SentData.objects.get_for_rec(rec).last_updated_on
                )

    def _pre_upload_clear_pbn_statements_if_any(self, rec):
        """Wycofaj oświadczenia z PBN PRZED wysyłką pracy bez-oświadczeniowej.

        Sytuacja docelowa: praca lokalnie ma już 0 dyscyplin (np. ostatnia
        została skasowana), a PBN nadal trzyma stare oświadczenia. POST
        do ``/v1/repositorium/publications`` może odrzucić publikację gdy
        ma już oświadczenia po stronie PBN — kasujemy je upfront.

        Algorytm (best-effort):

        - Brak ``pbn_uid_id`` → praca jeszcze nie ma odpowiednika w PBN,
          nie ma czego kasować.
        - GET ``/page/statements`` z PBN. Gdy zawiedzie — log warning
          i kontynuujemy (``upload_publication`` rzuci czytelny błąd
          POST jeśli problem rzeczywiście blokuje wysyłkę).
        - Gdy PBN puste — nie ma czego kasować, return.
        - W przeciwnym razie DELETE selektywnie/batch (wg
          ``Uczelnia.pbn_kasuj_dyscypliny_selektywnie``). DELETE failure
          rzucamy w górę (``StatementsResendFailedException``) bo nie
          chcemy wysłać publikacji do API które za chwilę odrzuci nas
          z powodu pozostałych oświadczeń.
        """
        pbn_uid = rec.pbn_uid_id
        if not pbn_uid:
            return

        publication_pk = rec.pk
        try:
            pbn_statements = list(
                self.get_institution_statements_of_single_publication(
                    str(pbn_uid), 5120
                )
            )
        except Exception as e:
            logger.warning(
                "Pre-upload GET oświadczeń PBN dla %s nieudany (%s). "
                "Kontynuuję wysyłkę — POST może rzucić błąd jeśli PBN "
                "ma stare statements.",
                pbn_uid,
                e,
            )
            return

        if not pbn_statements:
            return

        uczelnia = self.uczelnia
        kasuj_selektywnie = (
            uczelnia.pbn_kasuj_dyscypliny_selektywnie if uczelnia else True
        )

        if kasuj_selektywnie:
            self._delete_statements_selective(
                str(pbn_uid), pbn_statements, publication_pk
            )
        else:
            try:
                self._delete_statements_batch(str(pbn_uid), publication_pk)
            except CannotDeleteStatementsException:
                # PBN mówi, że nie ma oświadczeń — akceptowalne (race
                # między naszym GET-em a kasowaniem przez kogoś innego).
                pass

    def upload_publication(
        self,
        rec,
        force_upload=False,
        export_pk_zero=None,
        always_affiliate_to_uid=None,
        max_retries_on_validation_error=3,  # DEPRECATED: nieużywany, backward compat
    ):
        """Wysyła publikację do PBN.

        Wybór endpointu zależy od obecności lokalnych oświadczeń:

        - Praca z lokalnymi statements → ``POST /v1/publications``
          (all-in-one, surowy payload z adaptera; statements w body).
        - Praca bez lokalnych statements (uczelnia z
          ``pbn_wysylaj_bez_oswiadczen=True``) →
          ``POST /v1/repositorium/publications`` (po konwersji
          ``convert_json_with_statements_to_no_statements`` + body
          owinięte w listę).

        Niezależnie od endpointu, ``sync_publication`` PO udanej wysyłce
        synchronizuje oświadczenia osobno przez
        ``/api/v2/institution-profile/statements`` (GET → diff →
        DELETE/POST). Dla ``/v1/publications`` typowo no-op (PBN ma
        identyczne statements z body); dla ``/v1/repositorium`` z
        lokalnym brakiem statements — kasuje pozostałe stare statements
        z PBN, jeśli były.

        Dla ścieżki repo dodatkowo wykonujemy **pre-upload clear**
        (``_pre_upload_clear_pbn_statements_if_any``): gdy praca ma
        ``pbn_uid_id`` i PBN ma jakieś oświadczenia — kasujemy je PRZED
        POST. Powód: endpoint ``/v1/repositorium/publications`` może
        odrzucić publikację gdy PBN ma istniejące oświadczenia, a my
        chcemy je usunąć (bo BPP nie ma intencji ich wysłania).

        Zwraca ``(objectId, ret, js, bez_oswiadczen)``.
        """
        js, bez_oswiadczen = self._prepare_publication_json(
            rec, export_pk_zero, always_affiliate_to_uid
        )
        self._check_upload_needed(rec, js, force_upload)

        if bez_oswiadczen:
            self._pre_upload_clear_pbn_statements_if_any(rec)

        endpoint_path = (
            PBN_POST_PUBLICATION_NO_STATEMENTS_URL
            if bez_oswiadczen
            else PBN_POST_PUBLICATIONS_URL
        )
        api_url = self.transport.base_url + endpoint_path
        SentData.objects.create_or_update_before_upload(rec, js, api_url=api_url)

        try:
            ret, objectId = self._post_publication_data(js, bez_oswiadczen)
            SentData.objects.mark_as_successful(rec, api_response_status=str(ret))
        except HttpException as e:
            SentData.objects.mark_as_failed(
                rec, exception=str(e), api_response_status=e.content
            )
            raise
        except Exception as e:
            SentData.objects.mark_as_failed(rec, exception=str(e))
            raise

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

    def _build_post_statements_payload(self, rec, filter_keys=None):
        """Buduje payload dla ``POST /api/v2/institution-profile/statements``.

        Gdy ``filter_keys`` jest ``None``, zwraca pełen payload z
        ``WydawnictwoPBNAdapter.pbn_get_api_statements()`` (wszystkie
        lokalne statements w formacie zgodnym z endpointem).

        Gdy ``filter_keys`` to set tupli
        ``(personObjectId_str, disciplineId_str)``:

        - ``publicationUuid`` bierzemy z wynikowego ``pbn_get_api_statements``
          (to również wymusza wywołanie ``get_pbn_uuid`` w adapterze —
          jeśli nie ma V2 lokalnie, rzuci ``DaneLokalneWymagajaAktualizacjiException``).
        - Statements bierzemy z surowego ``pbn_get_json_statements()`` (format
          przed konwersją, zawiera ``disciplineId`` używany jako część klucza
          porównania). Filtrujemy po ``_statement_key_intended`` i przepuszczamy
          każdy przez ``_convert_stmt_for_api``.

        Zwraca ``None`` gdy zestaw po filtrowaniu jest pusty (brak sensu
        POST-ować pustą listę).
        """
        adapter = WydawnictwoPBNAdapter(rec, uczelnia=self.uczelnia)

        # Zawsze wywołujemy pbn_get_api_statements — daje publicationUuid
        # i pełen zestaw dla trybu bez-filtra. Może rzucić
        # DaneLokalneWymagajaAktualizacjiException — propaguje do callera.
        full_payload = adapter.pbn_get_api_statements()

        if filter_keys is None:
            # Pełen zestaw (tryb batch — po delete_all POST-ujemy wszystko).
            return full_payload

        if not filter_keys:
            return None

        # Filtrowanie po kluczu ``(personObjectId, disciplineId)``.
        # Klucz wymaga surowego disciplineId (``pbn_get_api_statements``
        # usuwa disciplineId gdy jest disciplineUuid, więc nie da się
        # filtrować po full_payload).
        filtered = [
            self._convert_stmt_for_api(s)
            for s in adapter.pbn_get_json_statements()
            if self._statement_key_intended(s) in filter_keys
        ]
        if not filtered:
            return None
        return {
            "publicationUuid": full_payload["publicationUuid"],
            "statements": filtered,
        }

    def _post_statements_with_retry(
        self, rec, objectId, publication_pk, filter_keys=None, max_tries=3
    ):
        """POST oświadczeń publikacji do ``/api/v2/institution-profile/statements``.

        Args:
            rec: rekord BPP (Wydawnictwo_Ciagle/Wydawnictwo_Zwarte).
            objectId: PBN UID publikacji (do logowania błędów).
            publication_pk: PK rekordu BPP (do logowania błędów).
            filter_keys: Optional[set] zestaw kluczy
                ``(personObjectId_str, disciplineId_str)`` — gdy podany,
                POST-ujemy tylko te statements których klucz jest w zestawie
                (używane w krokach 3/4b algorytmu — wysyłamy tylko brakujące
                w PBN, nie dublujemy istniejących). Gdy ``None`` — POST-ujemy
                pełen zestaw lokalnych (używane w trybie batch).
            max_tries: liczba prób retry (default 3).

        Wymaga lokalnego ``PublikacjaInstytucji_V2`` (wywołanie
        ``get_pbn_uuid`` rzuca ``DaneLokalneWymagajaAktualizacjiException``
        gdy brak) — ``sync_publication`` wywołuje ``pobierz_publikacje_instytucji_v2``
        przed tym helperem, więc V2 powinno istnieć.

        Retry z exponential backoff. Po wyczerpaniu: rollbar + raise
        ``StatementsResendFailedException``.

        Gdy ``filter_keys`` jest pustym setem albo po filtrowaniu zestaw
        jest pusty — metoda nie wykonuje POST-a (brak czego wysłać).
        """
        # _build_post_statements_payload może rzucić
        # DaneLokalneWymagajaAktualizacjiException — propaguje do callera
        # (sync_publication), który loguje warning zamiast crash.
        payload = self._build_post_statements_payload(rec, filter_keys=filter_keys)
        if payload is None:
            return  # nic do wysłania

        body = {"data": [payload]}

        last_error = None
        for attempt in range(max_tries):
            try:
                self.post_discipline_statements(body)
                return
            except Exception as e:
                last_error = e
                logger.warning(
                    "Błąd POST oświadczeń dla %s, próba %d/%d: %s",
                    objectId,
                    attempt + 1,
                    max_tries,
                    e,
                    exc_info=True,
                )
                if attempt < max_tries - 1:
                    time.sleep(self._STATEMENT_RETRY_DELAYS[attempt])

        self._report_statements_failure_and_raise(publication_pk, objectId, last_error)

    def _sync_statements_with_pbn(
        self, rec, objectId, kasuj_selektywnie, notificator=None
    ):
        """Synchronizuje oświadczenia publikacji z PBN po wysyłce publikacji.

        Algorytm:
        1. GET aktualnych oświadczeń z PBN
        2. Intencja BPP z ``WydawnictwoPBNAdapter.pbn_get_json_statements()``
        3. Diff (klucz: person mongoId + numerek dyscypliny)
        4a. PBN ma + BPP nie chce → DELETE (selektywnie lub batch)
        4b. PBN nie ma + BPP chce → POST /v2/statements
        4c. Różnice (oba) → DELETE brakujących + POST dodatkowych
        4d. Identyczne → nic

        Args:
            rec: rekord BPP (Wydawnictwo_Ciagle/Wydawnictwo_Zwarte)
            objectId: PBN UID publikacji
            kasuj_selektywnie: True=per-osoba DELETE, False=batch delete_all
            notificator: opcjonalny logger UI

        Raises:
            StatementsResendFailedException: gdy retry operacji się wyczerpie
            DaneLokalneWymagajaAktualizacjiException: gdy POST potrzebuje
                V2 którego nie ma lokalnie (propagowana — caller loguje
                warning zamiast crashować)
        """
        publication_pk = rec.pk

        pbn_statements = self._get_pbn_statements_with_retry(objectId, publication_pk)
        intended = WydawnictwoPBNAdapter(
            rec, uczelnia=self.uczelnia
        ).pbn_get_json_statements()

        only_in_pbn, only_in_intended = self._diff_statements(pbn_statements, intended)

        if not only_in_pbn and not only_in_intended:
            if notificator is not None:
                notificator.info(
                    "Oświadczenia w PBN identyczne z intencją BPP — bez zmian."
                )
            return

        if only_in_pbn:
            if kasuj_selektywnie:
                # Zbuduj listę oświadczeń do usunięcia z PBN (pełne dict-y
                # zachowują personId + type, potrzebne dla delete_publication_statement).
                stmts_to_delete = [
                    s
                    for s in pbn_statements
                    if self._statement_key_pbn(s) in only_in_pbn
                ]
                self._delete_statements_selective(
                    objectId, stmts_to_delete, publication_pk
                )
            else:
                try:
                    self._delete_statements_batch(objectId, publication_pk)
                except CannotDeleteStatementsException:
                    # PBN mówi że nie ma oświadczeń — akceptowalne, kontynuuj
                    pass

        if only_in_intended:
            if kasuj_selektywnie:
                # Selective (kroki 3 i 4b algorytmu): wyślij TYLKO oświadczenia
                # brakujące w PBN (``only_in_intended``). Nie dublujemy już
                # istniejących — zakładamy że API PBN może sobie z duplikatami
                # nie radzić (idempotentność nie jest gwarantowana). Ten sam
                # filter działa dla obu scenariuszy (PBN puste vs PBN+BPP
                # różnią się), bo w obu ``only_in_intended`` reprezentuje
                # dokładnie "co trzeba dodać do PBN".
                self._post_statements_with_retry(
                    rec,
                    objectId,
                    publication_pk,
                    filter_keys=only_in_intended,
                )
            else:
                # Batch: po ``delete_all`` PBN jest puste, więc POST-ujemy
                # pełen zestaw lokalny (wipe+rewrite). Bez filtra.
                self._post_statements_with_retry(rec, objectId, publication_pk)

        if notificator is not None:
            notificator.info(
                f"Zsynchronizowano oświadczenia: "
                f"skasowano z PBN {len(only_in_pbn)}, "
                f"dodano do PBN {len(only_in_intended)}."
            )

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

        # Retry z exponential backoff dla V2 API
        max_v2_tries = 5
        v2_try = 0
        base_delay = 2

        while v2_try < max_v2_tries:
            try:
                self.pobierz_publikacje_instytucji_v2(objectId=objectId)
                return
            except PublikacjaInstytucjiV2NieZnalezionaException:
                v2_try += 1
                if v2_try >= max_v2_tries:
                    notificator.error(
                        f"Po {max_v2_tries} próbach nie znaleziono oświadczeń V2 w PBN. "
                        "Może to oznaczać że: (1) publikacja nie ma jeszcze oświadczeń, "
                        "(2) PBN jeszcze ich nie wygenerował. "
                        "Spróbuj ponownie za kilka minut lub użyj wysyłki w tle "
                        "(PBN Export Queue), która automatycznie poradzi sobie z tym przypadkiem."
                    )
                    return

                delay = base_delay * (2**v2_try)
                logger.info(
                    f"V2 API nie gotowe dla objectId={objectId}, "
                    f"próba {v2_try}/{max_v2_tries}, czekam {delay}s"
                )
                time.sleep(delay)

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
        delete_statements_before_upload=False,  # DEPRECATED: ignorowany
        export_pk_zero=None,
        always_affiliate_to_uid=None,
    ):
        """
        Synchronizuje publikację BPP z PBN w dwóch niezależnych krokach:

        1. POST publikacji — endpoint zależy od obecności lokalnych
           oświadczeń (``upload_publication`` decyduje):
           - praca z statements → ``/v1/publications`` (all-in-one);
           - praca bez statements (flaga uczelni
             ``pbn_wysylaj_bez_oswiadczen=True``) →
             ``/v1/repositorium/publications``.
        2. Synchronizacja oświadczeń (po sukcesie kroku 1): GET aktualnego
           stanu w PBN, porównanie z intencją BPP, selektywne DELETE/POST.
           Działa dla obu endpointów — po ``/v1/publications`` typowo no-op
           (PBN ma już identyczne statements z body), po
           ``/v1/repositorium`` z lokalnym brakiem statements: kasuje
           ewentualne pozostałości z PBN.

        Gdy POST publikacji zawiedzie — oświadczenia w PBN pozostają
        nietknięte (ważna gwarancja bezpieczeństwa). Gdy POST publikacji
        OK ale synchronizacja oświadczeń nie — rzuca
        ``StatementsResendFailedException`` (klasyfikowane w
        ``pbn_export_queue`` jako RETRY_LATER).

        :param delete_statements_before_upload: DEPRECATED, ignorowany —
            zachowany w sygnaturze dla backward compat. Nowa logika zawsze
            synchronizuje oświadczenia po wysyłce publikacji (split flow),
            a tryb kasowania sterowany jest przez
            ``Uczelnia.pbn_kasuj_dyscypliny_selektywnie``.
        """
        pub = self.eventually_coerce_to_publication(pub)

        # KROK 1: POST publikacji do endpointu repo (zawsze)
        objectId, ret, js, _bez_oswiadczen = self.upload_publication(
            pub,
            force_upload=force_upload,
            export_pk_zero=export_pk_zero,
            always_affiliate_to_uid=always_affiliate_to_uid,
        )

        if not objectId:
            self._handle_no_objectid(notificator, ret, js, pub)
            return

        # KROK 2: pobierz lokalnie Publication (obiekt mongodb)
        publication = self.download_publication(objectId=objectId)

        # Update SentData with the publication link now that it exists
        try:
            sent_data = SentData.objects.get_for_rec(pub)
            if sent_data.pbn_uid_id is None:
                sent_data.pbn_uid_id = publication.pk
                sent_data.save()
        except SentData.DoesNotExist:
            # This shouldn't happen if upload_publication was called
            pass

        # KROK 3: obsługa zmiany/konfliktu PBN UID
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

        # KROK 4: pobierz lokalnie PublikacjaInstytucji_V2 (wymagane przez
        # ``pbn_get_api_statements`` w ``_post_statements_with_retry``).
        # Przy okazji odświeża lokalny cache ``OswiadczenieInstytucji``
        # (best effort — błąd tu nie blokuje synchronizacji oświadczeń,
        # bo ``_sync_statements_with_pbn`` zrobi własne GET dla porównania).
        try:
            self._download_statements_with_retry(publication, objectId, notificator)
        except Exception as e:
            logger.warning(
                "Odświeżenie lokalnego cache oświadczeń dla %s nie powiodło się: %s",
                objectId,
                e,
            )

        # KROK 5: synchronizacja oświadczeń (split flow, po wysyłce publikacji)
        uczelnia = self.uczelnia
        kasuj_selektywnie = (
            uczelnia.pbn_kasuj_dyscypliny_selektywnie if uczelnia else True
        )
        try:
            self._sync_statements_with_pbn(
                pub, objectId, kasuj_selektywnie, notificator
            )
        except DaneLokalneWymagajaAktualizacjiException as e:
            # Brak lokalnego PublikacjaInstytucji_V2 — nie da się wysłać
            # oświadczeń. Logujemy warning i kontynuujemy (publikacja
            # została już wysłana w KROK 1, to nie jest fatal error).
            logger.warning("Brak V2 dla %s — pomijam sync oświadczeń: %s", objectId, e)
            if notificator is not None:
                notificator.warning(
                    f"Nie mogę zsynchronizować oświadczeń (brak lokalnych "
                    f"danych V2): {e}"
                )

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
