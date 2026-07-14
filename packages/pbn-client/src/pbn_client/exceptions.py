"""Exceptions raised by the framework-independent PBN protocol client."""

import json

__all__ = [
    "AccessDeniedException",
    "AuthenticationConfigurationError",
    "AuthenticationResponseError",
    "CannotDeleteStatementsException",
    "CannotUploadPublicationFee",
    "HttpException",
    "NeedsPBNAuthorisationException",
    "PBNValidationError",
    "PraceSerwisoweException",
    "PublicationDoesNotExistInInstitutionProfile",
    "ResourceLockedException",
    "SciencistDoesNotExist",
    "StatementsResendFailedException",
    "parse_pbn_validation_details",
]


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


class SciencistDoesNotExist(Exception):
    """The requested scientist does not exist in PBN."""


class AuthenticationConfigurationError(Exception):
    pass


class AuthenticationResponseError(Exception):
    pass


class NeedsPBNAuthorisationException(HttpException):
    pass


class CannotUploadPublicationFee(ValueError):
    """PBN rejected a fee because the publication has no fee obligation."""


class PublicationDoesNotExistInInstitutionProfile(ValueError):
    """The publication is missing from the PBN institution profile."""


class StatementsResendFailedException(Exception):
    """Statement synchronization failed after exhausting its retry policy."""

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
    """Return deduplicated PBN validation messages or ``None``.

    Recognizes both the object-shaped ``details`` response and the list-shaped
    response containing ``message``, ``description`` or ``code`` fields.
    Hostile values are converted to strings and malformed elements are skipped.
    """

    def _coerce(value):
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in value)
        return str(value)

    messages = []
    if isinstance(parsed_json, dict):
        details = parsed_json.get("details")
        if isinstance(details, dict) and details:
            messages = [_coerce(value) for value in details.values()]
    elif isinstance(parsed_json, list) and parsed_json:
        for element in parsed_json:
            if not isinstance(element, dict):
                continue
            text = (
                element.get("message")
                or element.get("description")
                or element.get("code")
            )
            if text:
                messages.append(_coerce(text))

    if not messages:
        return None
    return list(dict.fromkeys(messages))


class PBNValidationError(HttpException):
    """PBN rejected user data with a validation response.

    ``__str__`` intentionally remains inherited. BPP's compatibility layer
    parses the original exception tuple and requires the raw response body.
    """

    def __init__(self, status_code, url, content):
        super().__init__(status_code, url, content)
        self.messages = parse_pbn_validation_details(self.json) or []

    def user_messages(self):
        """Return deduplicated messages suitable for display to a user."""

        return self.messages
