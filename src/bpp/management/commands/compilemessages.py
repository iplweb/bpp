"""``compilemessages`` kompilujący .po → .mo w czystym Pythonie (Babel).

Override komendy ``django.core`` o tej samej nazwie — aplikacja ``bpp`` jest
w ``INSTALLED_APPS``, więc ``get_commands()`` wybiera tę implementację zamiast
wbudowanej. Dzięki temu wszystkie istniejące wywołania (``manage.py
compilemessages -l pl ...`` w Makefile i Dockerfile) działają bez zmian.

Cel: usunąć zależność od systemowego pakietu apt ``gettext`` (binarka
``msgfmt``), którą wbudowany ``compilemessages`` woła przez ``subprocess``.
Babel kompiluje katalog w czystym Pythonie, więc obraz Dockera nie musi już
instalować ``gettext`` (oszczędność apt-a; binarki C → mały wheel).

Ponownie używamy CAŁEJ logiki wykrywania plików ``.po`` + parsowania flag
(``--locale``, ``--ignore``, ``--exclude``) z klasy bazowej — nadpisujemy
tylko (a) sondowanie obecności binarki ``msgfmt`` i (b) sam krok kompilacji.

Uwaga: ``makemessages`` (xgettext/msgmerge) NIE jest tu ruszany — to operacja
dev-only, nieobecna w buildzie/CI. Deweloper regenerujący ``.po`` ze źródeł
nadal potrzebuje lokalnie GNU gettext (albo ``pybabel extract``).
"""

from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po
from django.core.management.commands import compilemessages as dj_compilemessages


class Command(dj_compilemessages.Command):
    help = "Kompiluje pliki .po do .mo w czystym Pythonie (Babel, bez msgfmt)."

    def handle(self, **options):
        # Bazowe ``handle()`` przerywa z CommandError, jeśli binarki ``msgfmt``
        # nie ma na PATH. Kompilujemy Babelem, więc neutralizujemy tę sondę na
        # czas wywołania — zamiast kopiować ~50 linii logiki wykrywania locale
        # (którą chcemy reużyć w całości, łącznie z ``--ignore``/``--locale``).
        original_find_command = dj_compilemessages.find_command
        dj_compilemessages.find_command = lambda program: program  # zawsze „jest"
        try:
            super().handle(**options)
        finally:
            dj_compilemessages.find_command = original_find_command

    def compile_messages(self, locations):
        """Kompiluje listę krotek ``[(katalog, plik.po), ...]`` Babelem.

        Zachowuje semantykę bazową: pomija ``.mo`` świeższe niż ``.po`` oraz
        honoruje ``--use-fuzzy`` (bazowa klasa dokleja ``-f`` do
        ``program_options``).
        """
        use_fuzzy = "-f" in self.program_options
        for dirpath, filename in locations:
            po_path = Path(dirpath) / filename
            mo_path = po_path.with_suffix(".mo")

            try:
                if mo_path.stat().st_mtime >= po_path.stat().st_mtime:
                    if self.verbosity > 0:
                        self.stdout.write(
                            f'File "{po_path}" is already compiled and up to date.'
                        )
                    continue
            except FileNotFoundError:
                pass

            if self.verbosity > 0:
                self.stdout.write(f"processing file {filename} in {dirpath}")

            with po_path.open("rb") as po_file:
                catalog = read_po(po_file)

            # Autorytatywne locale katalogu to nazwa katalogu w ścieżce
            # ``locale/<locale>/LC_MESSAGES/`` — nie nagłówek ``Language:``,
            # który Django generuje pusty. Babel emituje nagłówek
            # ``Plural-Forms`` do .mo TYLKO gdy ``catalog.locale`` jest
            # ustawione; bez tego cicho degraduje do germańskich 2 form i
            # polskie liczebniki (4 formy) renderują się błędnie. Ustawiamy
            # je więc jawnie ze ścieżki, odtwarzając zachowanie ``msgfmt``
            # (który nagłówek Plural-Forms kopiuje dosłownie).
            catalog.locale = po_path.parent.parent.name

            with mo_path.open("wb") as mo_file:
                write_mo(mo_file, catalog, use_fuzzy=use_fuzzy)
