import json


class TlumaczDyscyplinException(ValueError):
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


class AccessDeniedException(Exception):
    def __init__(self, url, content):
        self.url = url
        self.content = content


class BrakIDPracyPoStroniePBN(HttpException):
    pass


class SciencistDoesNotExist(Exception):
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
