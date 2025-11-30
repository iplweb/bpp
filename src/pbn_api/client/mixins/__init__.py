"""API endpoint mixins for PBN client."""

from .conferences import ConferencesMixin
from .dictionaries import DictionariesMixin
from .institutions import InstitutionsMixin, InstitutionsProfileMixin
from .journals import JournalsMixin
from .person import PersonMixin
from .publications import PublicationsMixin
from .publishers import PublishersMixin
from .search import SearchMixin

__all__ = [
    "ConferencesMixin",
    "DictionariesMixin",
    "InstitutionsMixin",
    "InstitutionsProfileMixin",
    "JournalsMixin",
    "PersonMixin",
    "PublicationsMixin",
    "PublishersMixin",
    "SearchMixin",
]
