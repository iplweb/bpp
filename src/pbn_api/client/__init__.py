"""
PBN API Client package.

This module provides the PBNClient class for interacting with the Polish Bibliography
Network (PBN) API.
"""

from pbn_client import PBNClient
from pbn_client.auth import OAuthMixin

# Re-export constants for backwards compatibility
# (previously these were importable from pbn_api.client)
from pbn_client.const import (
    DEFAULT_BASE_URL,
    NEEDS_PBN_AUTH_MSG,
    PBN_DELETE_PUBLICATION_STATEMENT,
    PBN_GET_DISCIPLINES_URL,
    PBN_GET_INSTITUTION_PUBLICATIONS_V2,
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_GET_JOURNAL_BY_ID,
    PBN_GET_LANGUAGES_URL,
    PBN_GET_PUBLICATION_BY_ID_URL,
    PBN_POST_INSTITUTION_STATEMENTS_URL,
    PBN_POST_PUBLICATION_FEE_URL,
    PBN_POST_PUBLICATION_NO_STATEMENTS_URL,
    PBN_POST_PUBLICATIONS_URL,
    PBN_SEARCH_PUBLICATIONS_URL,
)
from pbn_client.mixins import (
    ConferencesMixin,
    DictionariesMixin,
    InstitutionsMixin,
    InstitutionsProfileMixin,
    JournalsMixin,
    PersonMixin,
    PublicationsMixin,
    PublishersMixin,
    SearchMixin,
)
from pbn_client.pagination import PageableResource
from pbn_client.transport import PBNClientTransport, RequestsTransport
from pbn_client.utils import smart_content

from .disciplines import DisciplinesMixin
from .publication_sync import PublicationSyncMixin

__all__ = [
    # Client classes
    "PBNClient",
    "BppPBNClient",
    "PBNClientTransport",
    "RequestsTransport",
    "PageableResource",
    "smart_content",
    # Mixins
    "OAuthMixin",
    "ConferencesMixin",
    "DictionariesMixin",
    "InstitutionsMixin",
    "InstitutionsProfileMixin",
    "JournalsMixin",
    "PersonMixin",
    "PublicationsMixin",
    "PublishersMixin",
    "SearchMixin",
    # Constants (backwards compatibility)
    "DEFAULT_BASE_URL",
    "NEEDS_PBN_AUTH_MSG",
    "PBN_DELETE_PUBLICATION_STATEMENT",
    "PBN_GET_DISCIPLINES_URL",
    "PBN_GET_INSTITUTION_PUBLICATIONS_V2",
    "PBN_GET_INSTITUTION_STATEMENTS",
    "PBN_GET_JOURNAL_BY_ID",
    "PBN_GET_LANGUAGES_URL",
    "PBN_GET_PUBLICATION_BY_ID_URL",
    "PBN_POST_INSTITUTION_STATEMENTS_URL",
    "PBN_POST_PUBLICATION_FEE_URL",
    "PBN_POST_PUBLICATION_NO_STATEMENTS_URL",
    "PBN_POST_PUBLICATIONS_URL",
    "PBN_SEARCH_PUBLICATIONS_URL",
]


class BppPBNClient(PBNClient, PublicationSyncMixin, DisciplinesMixin):
    """Klient PBN świadomy konkretnej ``Uczelnia`` (Warstwa 2, BPP-aware).

    Dziedziczy czyste operacje protokołu z ``pbn_client.PBNClient`` i dokłada
    orchestrację synchronizacji BPP↔PBN (``PublicationSyncMixin`` +
    ``DisciplinesMixin``). ``uczelnia`` jest JEDYNYM źródłem prawdy o uczelni —
    orchestracja czyta z niej flagi zamiast zgadywać ``get_default()``.
    """

    def __init__(self, transport, uczelnia):
        super().__init__(transport)
        self.uczelnia = uczelnia
