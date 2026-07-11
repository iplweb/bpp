import json


class AlreadyEnqueuedError(Exception):
    pass


class CharakterFormalnyNieobslugiwanyError(Exception):
    pass


class TlumaczDyscyplinException(ValueError):
    pass


class BrakZdefiniowanegoObiektuUczelniaWSystemieError(Exception):
    pass


class PraceSerwisoweException(Exception):
    def __str__(self):
        return "Po stronie PBN trwają prace serwisowe. Prosimy spróbować później. "


class CannotDeleteStatementsException(Exception):
    pass


class HttpException(Exception):
    def __init__(self, status_code, url, content):
        self.status_code = status_code
        self.url = url
        self.content = content
        try:
            self.json = json.loads(content[:4096])
        except (json.JSONDecodeError, ValueError, TypeError):
            self.json = None


class ResourceLockedException(HttpException):
    pass


class AccessDeniedException(Exception):
    def __init__(self, url, content):
        self.url = url
        self.content = content


class BrakIDPracyPoStroniePBN(HttpException):
    pass


class SciencistDoesNotExist(Exception):
    pass


class AuthenticationConfigurationError(Exception):
    pass


class AuthenticationResponseError(Exception):
    pass


class IntegracjaWylaczonaException(Exception):
    pass


class SameDataUploadedRecently(Exception):
    pass


class WillNotExportError(Exception):
    pass


class DOIorWWWMissing(WillNotExportError):
    pass


class LanguageMissingPBNUID(WillNotExportError):
    pass


class StatementsMissing(WillNotExportError):
    pass


class PKZeroExportDisabled(WillNotExportError):
    pass


class CharakterFormalnyMissingPBNUID(WillNotExportError):
    pass


class StatementDeletionError(Exception):
    def __init__(self, status_code, url, content):
        self.status_code = status_code
        self.url = url
        self.content = content


class NeedsPBNAuthorisationException(HttpException):
    pass


class NoFeeDataException(ValueError):
    pass


class NoPBNUIDException(ValueError):
    pass


class CannotUploadPublicationFee(ValueError):
    """Raised when PBN server indicates that publication is not subject to fee requirements."""

    pass


class PublicationDoesNotExistInInstitutionProfile(ValueError):
    """Raised when publication does not exist or is not in the institution profile."""

    pass


class PBNUIDChangedException(ValueError):
    """Podnoszony w sytuacji gdy wysłanej pracy która już posiada PBN UID należałoby zmienić PBN UID na inny
    na skutek odpowiedzi serwera. Technicznie nie jest to błąd i ten PBN UID jest ustawiany. Ten Exception
    jest używany przez Sentry do zgłoszenia (wysłania) sytuacji."""


class PBNUIDSetToExistentException(ValueError):
    """Podnoszony gdy wg serwera PBN pracy nowo wysyłanej nalezałoby ustawić PBN UID
    istniejącego rekordu. Używany do wysłania przez Sentry zgłoszenia o sytuacji."""


class DaneLokalneWymagajaAktualizacjiException(Exception):
    """Podnoszony, gdy lokalne dane powinny zostać zaktualizowane, aby odzwierciedlać
    zmiany po stronie PBN."""


class PublikacjaInstytucjiV2NieZnalezionaException(Exception):
    """Publikacja instytucji nie znaleziona po ID w api V2"""


class ZnalezionoWielePublikacjiInstytucjiV2Exception(Exception):
    pass


class BPPPublicationNotFound(Exception):
    """Publikacja z PBN nie ma odpowiednika w BPP."""

    pass


class BPPAutorNotFound(Exception):
    """Naukowiec z PBN nie ma odpowiednika w BPP."""

    pass


class BPPAutorPublicationLinkNotFound(Exception):
    """Autor istnieje w BPP, publikacja istnieje w BPP,
    ale autor nie jest powiązany z tą publikacją."""

    pass


class StatementsResendFailedException(Exception):
    """Podnoszony gdy synchronizacja oświadczeń z PBN nie powiodła się
    po wyczerpaniu prób retry w ``sync_publication`` (GET/DELETE/POST).

    Publikacja została już wysłana do PBN (POST do endpointu repo OK),
    ale kolejne kroki synchronizacji oświadczeń zawiodły. Klasyfikowany
    w ``pbn_export_queue`` jako RETRY_LATER + TECHNICZNY.
    """

    def __init__(self, publication_pk, pbn_uid, last_error):
        self.publication_pk = publication_pk
        self.pbn_uid = pbn_uid
        self.last_error = last_error
        super().__init__(
            f"Synchronizacja oświadczeń dla pracy pk={publication_pk} "
            f"(PBN UID={pbn_uid}) nie powiodła się po wyczerpaniu prób: "
            f"{last_error}"
        )


def parse_pbn_validation_details(parsed_json):
    """Zwraca zdeduplikowaną listę komunikatów walidacyjnych PBN, albo None
    gdy ``parsed_json`` nie jest odpowiedzią walidacyjną.

    Rozpoznaje dwa formaty odpowiedzi PBN:
    - Format 1: {"details": {pole: komunikat, ...}} — dict z niepustym details.
    - Format 2: [{"code": ..., "description": ...}, ...] — lista dict-ów;
      dla każdego elementu fallback message -> description -> code.

    Hostile-input-safe: wartości są koercowane do str (listy spłaszczane),
    elementy nie-dict w Format 2 pomijane. Żadne wejście nie wyrzuca wyjątku.
    Deduplikacja zachowuje pierwszą kolejność wystąpienia.
    """

    def _coerce(val):
        if isinstance(val, (list, tuple)):
            return ", ".join(str(v) for v in val)
        return str(val)

    messages = []
    if isinstance(parsed_json, dict):
        details = parsed_json.get("details")
        if isinstance(details, dict) and details:
            messages = [_coerce(v) for v in details.values()]
    elif isinstance(parsed_json, list) and parsed_json:
        for el in parsed_json:
            if not isinstance(el, dict):
                continue
            text = el.get("message") or el.get("description") or el.get("code")
            if text:
                messages.append(_coerce(text))

    if not messages:
        return None
    return list(dict.fromkeys(messages))


class PBNValidationError(HttpException):
    """PBN odrzucił dane (Validation failed). Błąd merytoryczny — dane do
    poprawienia przez użytkownika, NIE bug w kodzie.

    NIE nadpisujemy __str__: str(exc) musi dawać odziedziczoną tuplę
    (status, url, content), bo kolejka parsuje SentData.exception przez
    looks_like_tuple, a traceback ma zachować surowy JSON body.
    """

    def __init__(self, status_code, url, content):
        super().__init__(status_code, url, content)
        self.messages = parse_pbn_validation_details(self.json) or []

    def user_messages(self):
        """Zdeduplikowana lista czytelnych komunikatów dla użytkownika."""
        return self.messages
