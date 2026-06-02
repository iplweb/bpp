"""
PBN API Client package.

This module provides the PBNClient class for interacting with the Polish Bibliography
Network (PBN) API.
"""

import sys
from collections.abc import Iterable
from pprint import pprint

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


class PBNClient(
    ConferencesMixin,
    DictionariesMixin,
    InstitutionsMixin,
    InstitutionsProfileMixin,
    JournalsMixin,
    PersonMixin,
    PublicationsMixin,
    PublishersMixin,
    SearchMixin,
    PublicationSyncMixin,
    DisciplinesMixin,
):
    """Main client for interacting with the PBN API."""

    _interactive = False

    def __init__(self, transport: RequestsTransport):
        self.transport = transport

    def _get_command_function(self, cmd):
        """Get function to execute from command name."""
        try:
            return getattr(self, cmd[0])
        except AttributeError as e:
            if self._interactive:
                print(f"No such command: {cmd}")
                return None
            raise e

    def _extract_arguments(self, lst):
        """Extract positional and keyword arguments from command list."""
        args = ()
        kw = {}
        for elem in lst:
            if elem.find(":") >= 1:
                k, n = elem.split(":", 1)
                kw[k] = n
            else:
                args += (elem,)
        return args, kw

    def _print_non_interactive_result(self, res):
        """Print result in non-interactive mode."""
        import json

        print(json.dumps(res))

    def _print_interactive_result(self, res):
        """Print result in interactive mode."""
        if type(res) is dict:
            pprint(res)
        elif isinstance(res, Iterable):
            if self._interactive and hasattr(res, "total_elements"):
                print(
                    "Incoming data: no_elements=",
                    res.total_elements,
                    "no_pages=",
                    res.total_pages,
                )
                input("Press ENTER to continue> ")
            for elem in res:
                pprint(elem)

    def exec(self, cmd):
        fun = self._get_command_function(cmd)
        if fun is None:
            return

        args, kw = self._extract_arguments(cmd[1:])
        res = fun(*args, **kw)

        if not sys.stdout.isatty():
            self._print_non_interactive_result(res)
        else:
            self._print_interactive_result(res)

    def interactive(self):
        self._interactive = True
        while True:
            cmd = input("cmd> ")
            if cmd == "exit":
                break
            self.exec(cmd.split(" "))
