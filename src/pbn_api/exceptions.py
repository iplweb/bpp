"""BPP compatibility exceptions and PBN protocol exception re-exports."""

from pbn_client.exceptions import (
    AccessDeniedException,
    AuthenticationConfigurationError,
    AuthenticationResponseError,
    CannotDeleteStatementsException,
    CannotUploadPublicationFee,
    HttpException,
    NeedsPBNAuthorisationException,
    PBNValidationError,
    PraceSerwisoweException,
    PublicationDoesNotExistInInstitutionProfile,
    PublicationNotFound,
    ResourceLockedException,
    SciencistDoesNotExist,
    StatementsResendFailedException,
    parse_pbn_validation_details,
)

__all__ = [
    "AccessDeniedException",
    "AlreadyEnqueuedError",
    "AutorBezIdentyfikatoraPBN",
    "AuthenticationConfigurationError",
    "AuthenticationResponseError",
    "BPPAutorNotFound",
    "BPPAutorPublicationLinkNotFound",
    "BPPPublicationNotFound",
    "BrakIDPracyPoStroniePBN",
    "BrakZdefiniowanegoObiektuUczelniaWSystemieError",
    "CannotDeleteStatementsException",
    "CannotUploadPublicationFee",
    "CharakterFormalnyMissingPBNUID",
    "CharakterFormalnyNieobslugiwanyError",
    "DOIorWWWMissing",
    "DaneLokalneWymagajaAktualizacjiException",
    "HttpException",
    "IntegracjaWylaczonaException",
    "LanguageMissingPBNUID",
    "NeedsPBNAuthorisationException",
    "NoFeeDataException",
    "NoPBNUIDException",
    "PBNValidationError",
    "PBNUIDChangedException",
    "PBNUIDSetToExistentException",
    "PKZeroExportDisabled",
    "PraceSerwisoweException",
    "PublikacjaInstytucjiV2NieZnalezionaException",
    "PublicationDoesNotExistInInstitutionProfile",
    "PublicationNotFound",
    "ResourceLockedException",
    "SameDataUploadedRecently",
    "SciencistDoesNotExist",
    "StatementDeletionError",
    "StatementsMissing",
    "StatementsResendFailedException",
    "TlumaczDyscyplinException",
    "WillNotExportError",
    "ZnalezionoWielePublikacjiInstytucjiV2Exception",
    "parse_pbn_validation_details",
]


class AlreadyEnqueuedError(Exception):
    pass


class CharakterFormalnyNieobslugiwanyError(Exception):
    pass


class TlumaczDyscyplinException(ValueError):
    pass


class BrakZdefiniowanegoObiektuUczelniaWSystemieError(Exception):
    pass


# Alias zgodności: to DOKŁADNIE ta sama klasa co pakietowy
# ``pbn_client.PublicationNotFound`` (przypisanie, nie podklasa — ``is``),
# żeby istniejące handlery ``except BrakIDPracyPoStroniePBN`` łapały wyjątek
# rzucany RAZ w endpoincie paczki (``get_publication_by_id`` na PBN 422
# „was not exists!”). Rozpoznanie nie jest już duplikowane w call-site'ach
# BPP. Uwaga: to CO INNEGO niż ``BPPPublicationNotFound`` (brak rekordu po
# stronie BPP, nie PBN).
BrakIDPracyPoStroniePBN = PublicationNotFound


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


class AutorBezIdentyfikatoraPBN(WillNotExportError):
    """Praca ma autorów, których oświadczenia nie da się wysłać do PBN (FD#509).

    Autor afiliuje w jednostce skupiającej pracowników i ma w pracy przypiętą
    dyscyplinę, ale nie ma ani odpowiednika w PBN, ani ORCID — PBN nie miałby
    jak przypisać oświadczenia do osoby. Dawniej takie oświadczenie było po
    cichu pomijane, a praca szła do PBN bez niego; teraz wysyłka całej pracy
    jest zatrzymywana, dopóki ktoś nie uzupełni danych autora.

    ``autorzy`` to lista powiązań autor–rekord (``Wydawnictwo_*_Autor``).
    Komunikat tekstowy jest celowo JEDNOLINIOWY i krótki (najwyżej
    ``MAKS_NAZWISK`` nazwisk): kolejka eksportu wyłuskuje go z linii wyjątku
    w tracebacku i ucina komunikaty dłuższe niż 512 znaków.
    """

    MAKS_NAZWISK = 3

    def __init__(self, autorzy):
        self.autorzy = list(autorzy)
        nazwiska = [str(wa.autor) for wa in self.autorzy[: self.MAKS_NAZWISK]]
        reszta = len(self.autorzy) - len(nazwiska)
        kto = ", ".join(nazwiska)
        if reszta > 0:
            kto += f" (oraz {reszta} kolejnych)"
        super().__init__(
            "oświadczenia nie mogą zostać wysłane, bo autor nie ma ani "
            f"odpowiednika w PBN, ani ORCID: {kto}. Ustaw autorowi "
            "„Odpowiednik w PBN” albo wpisz ORCID i wyślij pracę ponownie; "
            "jeżeli osoba nie powinna być oświadczana, odepnij jej dyscyplinę "
            "albo popraw afiliację w tej pracy"
        )


class CharakterFormalnyMissingPBNUID(WillNotExportError):
    pass


class StatementDeletionError(Exception):
    def __init__(self, status_code, url, content):
        self.status_code = status_code
        self.url = url
        self.content = content


class NoFeeDataException(ValueError):
    pass


class NoPBNUIDException(ValueError):
    pass


class PBNUIDChangedException(ValueError):
    """A local publication should be updated to a different PBN UID."""


class PBNUIDSetToExistentException(ValueError):
    """A newly exported publication resolved to an existing PBN UID."""


class DaneLokalneWymagajaAktualizacjiException(Exception):
    """Local BPP data should be updated to match PBN."""


class PublikacjaInstytucjiV2NieZnalezionaException(Exception):
    """The requested institution publication was not found by BPP sync."""


class ZnalezionoWielePublikacjiInstytucjiV2Exception(Exception):
    pass


class BPPPublicationNotFound(Exception):
    """A PBN publication has no corresponding BPP publication."""


class BPPAutorNotFound(Exception):
    """A PBN scientist has no corresponding BPP author."""


class BPPAutorPublicationLinkNotFound(Exception):
    """BPP author and publication exist but are not linked."""
