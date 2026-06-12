"""Czysty klient protokołu PBN (Warstwa 1).

``PBNClient`` to kompozycja mixinów protokołu (słownikowo-CRUD + silnik
oświadczeń ``StatementsMixin``). Nie zna ``bpp`` ani obiektu ``Uczelnia`` —
operuje na tokenach, PBN UID-ach, JSON-ach i flagach bool.

Orchestracja synchronizacji BPP↔PBN (znająca rekord i ``Uczelnia``) żyje
w ``pbn_api/client`` jako ``BppPBNClient`` dziedziczący po tej klasie.

Patrz: docs/superpowers/specs/2026-06-02-pbn-client-split-design.md
"""

import sys
from collections.abc import Iterable
from pprint import pprint

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
from .statements import StatementsMixin
from .transport import RequestsTransport


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
    StatementsMixin,
):
    """Czysty klient protokołu PBN (bez orchestracji BPP, bez wiedzy o Uczelni)."""

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
