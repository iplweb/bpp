"""
Klasy bazowe dla management commands z lepszym formatowaniem pomocy.
"""

import argparse

from django.core.management.base import BaseCommand as DjangoBaseCommand


class RawTextHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """
    Formatter zachowujący formatowanie tekstu pomocy (nowe linie, wcięcia)
    ale jednocześnie prawidłowo formatujący argumenty.
    """

    def _fill_text(self, text, width, indent):
        """Zachowaj oryginalne formatowanie tekstu (nie zawijaj)."""
        return text

    def _split_lines(self, text, width):
        """Zachowaj oryginalne linie w opisach argumentów."""
        return text.splitlines()


class BaseCommand(DjangoBaseCommand):
    """
    Bazowa klasa dla management commands z lepszym formatowaniem pomocy.

    Używa RawTextHelpFormatter, który zachowuje:
    - Nowe linie w tekście pomocy
    - Wcięcia i formatowanie
    - Przykłady użycia w oryginalnej formie

    Użycie:
        from bpp.management.base import BaseCommand

        class Command(BaseCommand):
            help = '''
        Opis komendy z zachowanym formatowaniem.

        SEKCJA 1:
          --parametr1    Opis parametru
          --parametr2    Opis parametru

        PRZYKŁADY:
          python manage.py moja_komenda --parametr1 wartość
        '''
    """

    def create_parser(self, prog_name, subcommand, **kwargs):
        """Tworzy parser z customowym formatterem pomocy."""
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser
