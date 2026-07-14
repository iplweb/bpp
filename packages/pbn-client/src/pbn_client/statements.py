"""Silnik oświadczeń i czyste operacje publikacji PBN (Warstwa 1).

``StatementsMixin`` zawiera wyłącznie czyste operacje protokołu PBN: POST/GET
publikacji i opłat, konwersje JSON oraz silnik diff/DELETE/POST oświadczeń.
Operuje na PBN UID (string), słownikach JSON i flagach bool — nie zna ``bpp``
ani obiektu ``Uczelnia``.

Zależy (przez ``self``) od ``InstitutionsProfileMixin`` (metody
``delete_publication_statement``, ``delete_all_publication_statements``,
``get_institution_statements_of_single_publication``), dlatego musi być
komponowany razem z nim w ``PBNClient``.

Patrz: docs/superpowers/specs/2026-06-02-pbn-client-split-design.md
"""

import logging
import sys
import time

from pbn_client.const import (
    PBN_POST_PUBLICATION_FEE_URL,
    PBN_POST_PUBLICATION_NO_STATEMENTS_URL,
    PBN_POST_PUBLICATIONS_URL,
)
from pbn_client.dict_utils import rename_dict_key
from pbn_client.exceptions import (
    CannotDeleteStatementsException,
    CannotUploadPublicationFee,
    HttpException,
    PBNValidationError,
    PublicationDoesNotExistInInstitutionProfile,
    StatementsResendFailedException,
)
from pbn_client.reporting import default_reporter

# Backwards-compatible patch point; no external Rollbar dependency is imported.
rollbar = default_reporter

logger = logging.getLogger(__name__)


class StatementsMixin:
    """Czyste operacje publikacji i oświadczeń PBN (bez zależności od bpp)."""

    def post_publication(self, json):
        """POST publikacji wraz z oświadczeniami do ``/api/v1/publications``.

        Endpoint all-in-one — przyjmuje payload z kluczem ``statements``
        (pełny JSON publikacji wraz z oświadczeniami, bez konwersji pól ani
        owijania w listę). Zwraca pojedynczy obiekt z ``objectId`` (a nie
        listę z ``id`` jak endpoint repo).
        """
        return self.transport.post(PBN_POST_PUBLICATIONS_URL, body=json)

    def convert_json_with_statements_to_no_statements(self, json):
        # Endpoint repozytoryjny `/api/v1/repositorium/publications` nie
        # przyjmuje klucza `statements` w body — oświadczenia synchronizujemy
        # osobno przez `/api/v2/institution-profile/statements`.
        json.pop("statements", None)

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

        # OpenAccess releaseDateYear "2022" -> 2022 (int)
        # Jeśli konwersja na int zawiedzie — zachowujemy oryginalną wartość
        # (PBN zwróci validation error z jasnym komunikatem, jeśli format
        # jest nieprawidłowy). Wcześniejsza implementacja miała NameError:
        # zmienna ``i`` była zdefiniowana tylko wewnątrz ``try``, a
        # bezwarunkowy assignment poza blokiem rzucał NameError gdy
        # ``int()`` failowało.
        if json.get("openAccess", False) and isinstance(json["openAccess"], dict):
            value = json["openAccess"].get("releaseDateYear")
            if value is not None:
                try:
                    json["openAccess"]["releaseDateYear"] = int(value)
                except (ValueError, TypeError):
                    # Nie ruszamy wartości — PBN wskaże problem w walidacji.
                    pass
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
        try:
            return self.transport.post(
                PBN_POST_PUBLICATION_FEE_URL.format(id=publicationId), body=json
            )
        except HttpException as e:
            if e.status_code == 400:
                if e.content.find("nie jest objęta obowiązkiem") >= 0:
                    raise CannotUploadPublicationFee(
                        f"Publikacja {publicationId} nie jest objęta obowiązkiem "
                        f"wprowadzenia opłat za publikacje."
                    ) from e
                if e.content.find("nie znajduje się w Profilu Instytucji") >= 0:
                    raise PublicationDoesNotExistInInstitutionProfile(
                        f"Publikacja {publicationId} nie istnieje lub nie znajduje się "
                        f"w Profilu Instytucji."
                    ) from e
            raise

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

    def get_publication_fees_batch(self, publication_ids):
        """Get fees for multiple publications in a single API call.

        Args:
            publication_ids: List of publication IDs (PBN UIDs).

        Returns:
            Dict mapping publication_id to fee data, or empty dict if no fees.
        """
        if not publication_ids:
            return {}

        res = self.transport.post_pages(
            "/api/v1/institutionProfile/publications/search/fees",
            body={"publicationIds": [str(pid) for pid in publication_ids]},
        )

        # Build a mapping of publication ID -> fee data
        # Note: API returns publicationId nested in "publication" object
        fees_map = {}
        for item in res:
            publication = item.get("publication", {})
            pub_id = publication.get("publicationId") if publication else None
            if pub_id:
                fees_map[pub_id] = item

        return fees_map

    def _post_publication_data(self, js, bez_oswiadczen):
        """POST publikacji do właściwego endpointu i wyciągnięcie ``objectId``.

        - ``bez_oswiadczen=False`` → ``/v1/publications``,
          response: ``{"objectId": ...}`` (single dict).
        - ``bez_oswiadczen=True``  → ``/v1/repositorium/publications``,
          response: ``[{"id": ...}]`` (lista 1 elementu).
        """
        if not bez_oswiadczen:
            ret = self.post_publication(js)
            objectId = ret.get("objectId", None) if isinstance(ret, dict) else None
            return ret, objectId

        ret = self.post_publication_no_statements(js)
        if len(ret) != 1:
            raise Exception(
                "Lista zwróconych obiektów przy wysyłce pracy do repozytorium "
                "różna od jednego. "
                "Sytuacja nieobsługiwana, proszę o kontakt z autorem programu. "
            )
        try:
            objectId = ret[0].get("id", None)
        except (KeyError, IndexError) as e:
            raise Exception(f"Serwer zwrócił nieoczekiwaną odpowiedź. {ret=}") from e

        return ret, objectId

    def _delete_statements_with_retry(self, pbn_uid_id, max_tries=5):
        """Delete publication statements with retry on failure.

        Używane przez batch flow (``pbn_wysylka_oswiadczen/tasks.py``) oraz
        przez nowy ``_delete_statements_batch`` helper w ``sync_publication``.
        """
        no_tries = max_tries
        while True:
            try:
                self.delete_all_publication_statements(pbn_uid_id)
                return True
            except CannotDeleteStatementsException as e:
                # Warunek <= 0 (nie < 0): dla ``max_tries=5`` chcemy dokładnie
                # 5 prób (no_tries: 5→4→3→2→1→0), po szóstej iteracji rzucamy.
                # Wcześniejsze ``< 0`` pozwalało na 6 prób.
                if no_tries <= 0:
                    raise e
                no_tries -= 1
                time.sleep(0.5)

    # ----------- Helpery do nowego split-flow sync_publication -----------
    # Mapowanie kluczy porównania:
    # - PBN GET /page/statements zwraca: {personId, area, type, institutionId, ...}
    # - Adapter pbn_get_json_statements() zwraca: {personObjectId, disciplineId,
    #   disciplineUuid, type, ...}
    # Klucz porównania: (person mongoId, discipline numerek). Oba na string.
    # Selektywny DELETE używa (personId, role) — delete_publication_statement.

    _STATEMENT_RETRY_DELAYS = (2, 4, 8)  # exponential backoff przy 3 próbach

    @staticmethod
    def _statement_key_pbn(stmt):
        """Klucz porównania dla oświadczenia z PBN GET response."""
        return (
            str(stmt.get("personId", "")),
            str(stmt.get("area", "")),
        )

    @staticmethod
    def _statement_key_intended(stmt):
        """Klucz porównania dla oświadczenia z ``pbn_get_json_statements``."""
        return (
            str(stmt.get("personObjectId", "")),
            str(stmt.get("disciplineId", "")),
        )

    def _diff_statements(self, pbn_statements, intended_statements):
        """Porównuje zestaw oświadczeń PBN z intencją BPP.

        Zwraca (only_in_pbn, only_in_intended) jako sety kluczy
        ``(person_mongoId, discipline_numerek)``:

        - ``only_in_pbn`` — do usunięcia z PBN (PBN ma, BPP nie chce)
        - ``only_in_intended`` — do dodania do PBN (BPP chce, PBN nie ma)
        """
        pbn_keys = {self._statement_key_pbn(s) for s in pbn_statements}
        intended_keys = {self._statement_key_intended(s) for s in intended_statements}
        return pbn_keys - intended_keys, intended_keys - pbn_keys

    def _report_statements_failure_and_raise(
        self, publication_pk, objectId, last_error
    ):
        """Report a warning and raise ``StatementsResendFailedException``."""
        try:
            raise StatementsResendFailedException(publication_pk, objectId, last_error)
        except StatementsResendFailedException:
            reporter = getattr(self.transport, "reporter", rollbar)
            reporter.report_exc_info(
                sys.exc_info(),
                level="warning",
                extra_data={
                    "publication_pk": publication_pk,
                    "pbn_uid": str(objectId),
                    "last_error": str(last_error),
                },
            )
            raise

    def _get_pbn_statements_with_retry(self, objectId, publication_pk, max_tries=3):
        """Pobiera oświadczenia publikacji z PBN z retry (exponential backoff).

        Po wyczerpaniu prób: rollbar.report_exc_info(level="warning") oraz
        raise ``StatementsResendFailedException``.
        """
        last_error = None
        for attempt in range(max_tries):
            try:
                return list(
                    self.get_institution_statements_of_single_publication(
                        str(objectId), 5120
                    )
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "Błąd pobierania oświadczeń PBN dla %s, próba %d/%d: %s",
                    objectId,
                    attempt + 1,
                    max_tries,
                    e,
                    exc_info=True,
                )
                if attempt < max_tries - 1:
                    time.sleep(self._STATEMENT_RETRY_DELAYS[attempt])

        self._report_statements_failure_and_raise(publication_pk, objectId, last_error)

    def _delete_statements_selective(
        self, objectId, pbn_statements_to_delete, publication_pk, max_tries=3
    ):
        """Selektywne DELETE oświadczeń per-osoba (delete_publication_statement).

        Iteruje po liście oświadczeń PBN do usunięcia i wywołuje DELETE dla
        każdego (klucz: personId + type z PBN GET response). Po wyczerpaniu
        prób per oświadczenie: rollbar + raise StatementsResendFailedException.
        """
        for stmt in pbn_statements_to_delete:
            person_id = stmt.get("personId")
            role = stmt.get("type")
            last_error = None
            success = False
            for attempt in range(max_tries):
                try:
                    self.delete_publication_statement(str(objectId), person_id, role)
                    success = True
                    break
                except PBNValidationError:
                    raise
                except Exception as e:
                    last_error = e
                    logger.warning(
                        "Błąd DELETE oświadczenia (%s, %s) dla %s, próba %d/%d: %s",
                        person_id,
                        role,
                        objectId,
                        attempt + 1,
                        max_tries,
                        e,
                        exc_info=True,
                    )
                    if attempt < max_tries - 1:
                        time.sleep(self._STATEMENT_RETRY_DELAYS[attempt])
            if not success:
                self._report_statements_failure_and_raise(
                    publication_pk, objectId, last_error
                )

    def _delete_statements_batch(self, objectId, publication_pk, max_tries=3):
        """Batch DELETE wszystkich oświadczeń publikacji z retry.

        Rzuca ``CannotDeleteStatementsException`` w górę (caller może
        zignorować gdy PBN mówi że nie ma oświadczeń). Po wyczerpaniu prób
        dla innych błędów: rollbar + raise StatementsResendFailedException.
        """
        last_error = None
        for attempt in range(max_tries):
            try:
                self.delete_all_publication_statements(str(objectId))
                return
            except CannotDeleteStatementsException:
                raise
            except PBNValidationError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(
                    "Błąd batch DELETE oświadczeń dla %s, próba %d/%d: %s",
                    objectId,
                    attempt + 1,
                    max_tries,
                    e,
                    exc_info=True,
                )
                if attempt < max_tries - 1:
                    time.sleep(self._STATEMENT_RETRY_DELAYS[attempt])

        self._report_statements_failure_and_raise(publication_pk, objectId, last_error)

    @staticmethod
    def _convert_stmt_for_api(stmt):
        """Konwersja pojedynczego oświadczenia do formatu akceptowanego przez
        ``POST /api/v2/institution-profile/statements``.

        Wejście: oświadczenie w formacie generowanym przez warstwę wywołującą
        (klucze ``personObjectId``/``disciplineId``/``disciplineUuid``/``type``).
        Format wejścia musi pozostać zgodny z payloadem oświadczeń budowanym
        po stronie wołającego — przy zmianie jednego, zmień drugie.
        """
        stmt = dict(stmt)  # shallow copy — nie modyfikujemy oryginalnego
        if "disciplineId" in stmt and "disciplineUuid" in stmt:
            del stmt["disciplineId"]
        if "type" in stmt:
            stmt["personRole"] = stmt.pop("type")
        stmt.pop("personNaturalId", None)
        return stmt
