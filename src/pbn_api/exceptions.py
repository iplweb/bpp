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


class PBNUIDChangedException(ValueError):
    """Podnoszony w sytuacji gdy wysłanej pracy która już posiada PBN UID należałoby zmienić PBN UID na inny
    na skutek odpowiedzi serwera. Technicznie nie jest to błąd i ten PBN UID jest ustawiany. Ten Exception
    jest używany przez Sentry do zgłoszenia (wysłania) sytuacji."""


class PBNUIDSetToExistentException(ValueError):
    """Podnoszony gdy wg serwera PBN pracy nowo wysyłanej nalezałoby ustawić PBN UID
    istniejącego rekordu. Używany do wysłania przez Sentry zgłoszenia o sytuacji."""
