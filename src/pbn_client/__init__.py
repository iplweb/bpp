"""PBN API client — czysta warstwa protokołu (Warstwa 1, reusable).

Pakiet świadomie NIE zależy od ``bpp`` ani od ``pbn_api`` — to kandydat do
ekstrakcji jako osobny pakiet. Wie wyłącznie o pojęciach PBN: tokeny, URL-e,
PBN UID, JSON-y, flagi bool.

Patrz: docs/superpowers/specs/2026-06-02-pbn-client-split-design.md
"""

from .auth import OAuthMixin
from .client import PBNClient
from .mixins import (
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
from .pagination import PageableResource
from .transport import PBNClientTransport, RequestsTransport
from .utils import smart_content

__all__ = [
    "PBNClient",
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
    "PageableResource",
    "PBNClientTransport",
    "RequestsTransport",
    "smart_content",
]
