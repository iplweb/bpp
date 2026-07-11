"""``opisz_schemat_djangoql_dla_llm`` — BPP-owy bliźniak
``djangoql_describe_schema_for_llm``.

Zrzuca *ograniczoną* (allow-lista) przestrzeń wyszukiwania DjangoQL jako terse
opis dla LLM, ostemplowany wersją BPP. Domyślnie opisuje ``bpp.Rekord`` do
pliku ``src/bpp/data/rekord_djangoql_schema.compact.txt`` (commitowany
snapshot), który uczy model pisać zapytania DjangoQL wykonywane potem przez
endpointy ``/api/v1/zapytanie/{rekord,autor,autorzy}/`` oraz widok „Szukaj
zapytaniem".

Obsługuje trzy **kanoniczne korzenie** (``KORZENIE``): ``bpp.Rekord``,
``bpp.Autor``, ``bpp.Autorzy`` — wszystkie tym samym ``RekordLLMSchema``
(bezpieczna allow-lista + blocklist PII + no_value_targets), różni je tylko
model-korzeń. ``--wszystkie-korzenie`` generuje wszystkie trzy naraz; bez
``--output`` ścieżka jest wyprowadzana z ``--model``.

Różnice względem komendy z ``djangoql``:
- domyślnie używa ``bpp.djangoql_schema.RekordLLMSchema`` (allow-lista ~63
  modeli bibliograficznych zamiast ~214 osiągalnych domyślnie),
- nagłówek zawiera ``django_bpp.version.VERSION`` (bez znacznika czasu — diff
  między regeneracjami zostaje stabilny),
- domyślnie zapisuje do pliku (``--drukuj`` drukuje zamiast zapisu).

Przykłady::

    python manage.py opisz_schemat_djangoql_dla_llm
    python manage.py opisz_schemat_djangoql_dla_llm --wszystkie-korzenie
    python manage.py opisz_schemat_djangoql_dla_llm --model bpp.Autor --drukuj
    python manage.py opisz_schemat_djangoql_dla_llm --format json --drukuj
    python manage.py opisz_schemat_djangoql_dla_llm --max-fk-options 0
"""

import json
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.utils.module_loading import import_string
from djangoql.llm import describe_schema_for_llm
from djangoql.schema import DjangoQLSchema

from django_bpp.version import VERSION

DEFAULT_MODEL = "bpp.Rekord"
DEFAULT_SCHEMA = "bpp.djangoql_schema.RekordLLMSchema"
#: src/bpp/data/ (parents: commands→management→bpp). Katalog commitowanych snapshotów.
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
#: Kanoniczne korzenie eksportu → nazwa pliku artefaktu. Wszystkie trzy używają
#: TEGO SAMEGO ``RekordLLMSchema`` (bezpieczna allow-lista + blocklist PII +
#: no_value_targets + osadzanie wartości tylko dla bezpiecznych słowników);
#: różnią się WYŁĄCZNIE modelem-korzeniem. Dają round-trip dla trzech endpointów
#: ``/api/v1/zapytanie/{rekord,autor,autorzy}/`` — LLM dostaje pełny opis pól
#: każdego korzenia, nie tylko Rekordu.
KORZENIE = {
    "bpp.Rekord": "rekord_djangoql_schema.compact.txt",
    "bpp.Autor": "autor_djangoql_schema.compact.txt",
    "bpp.Autorzy": "autorzy_djangoql_schema.compact.txt",
}
DEFAULT_OUTPUT = DATA_DIR / KORZENIE[DEFAULT_MODEL]


class Command(BaseCommand):
    help = (
        "Zrzuca ograniczony (allow-lista) opis przestrzeni DjangoQL dla "
        "bpp.Rekord dla LLM, ostemplowany wersją BPP. Domyślnie zapisuje "
        "commitowany plik snapshotu."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            default=DEFAULT_MODEL,
            help='Model do opisania jako "app_label.ModelName" '
            "(domyślnie %(default)s).",
        )
        parser.add_argument(
            "--schema",
            default=DEFAULT_SCHEMA,
            help="Dotted path do podklasy DjangoQLSchema (domyślnie "
            "%(default)s — ograniczona allow-lista bez pickerów).",
        )
        parser.add_argument(
            "--format",
            dest="format",
            choices=["compact", "json"],
            default="compact",
            help="Format wyjścia: compact (domyślnie) lub json.",
        )
        parser.add_argument(
            "--max-fk-options",
            type=int,
            default=0,
            help="Maks. liczba wartości AUTO-osadzanych per relacja (domyślnie "
            "0 = tylko bezpieczne słowniki z fk_options; artefakt bez danych "
            "instytucji). >0 dodaje auto-wartości dla małych tabel — używaj "
            "lokalnie, NIE do commitowanego snapshotu (może osadzić tytuły "
            "publikacji/nazwiska z Twojej bazy).",
        )
        parser.add_argument(
            "--indent",
            type=int,
            default=2,
            help="Wcięcie JSON (domyślnie 2; tylko dla --format json).",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Ścieżka pliku wyjściowego. Domyślnie WYPROWADZANA z --model "
            "(kanoniczne korzenie rekord/autor/autorzy → pliki w src/bpp/data/); "
            "dla modelu spoza tej listy podaj ścieżkę jawnie.",
        )
        parser.add_argument(
            "--wszystkie-korzenie",
            dest="wszystkie_korzenie",
            action="store_true",
            help="Wygeneruj compact dla WSZYSTKICH kanonicznych korzeni naraz "
            "(rekord + autor + autorzy) do plików w src/bpp/data/ (lub --katalog). "
            "Ignoruje --model / --output / --drukuj / --format.",
        )
        parser.add_argument(
            "--katalog",
            default=None,
            help="Katalog wyjściowy dla --wszystkie-korzenie (domyślnie "
            "src/bpp/data/). Użyteczne w testach.",
        )
        parser.add_argument(
            "--drukuj",
            dest="to_stdout",
            action="store_true",
            help="Drukuj na stdout zamiast zapisu do pliku. (Nie nazywamy tej "
            "flagi --stdout: kolidowałaby z zarezerwowanym strumieniem stdout "
            "obsługiwanym przez call_command.)",
        )

    def handle(self, *args, **options):
        if options["wszystkie_korzenie"]:
            self._generuj_wszystkie(options)
            return

        model = self._resolve_model(options["model"])
        schema_cls = self._resolve_schema(options["schema"])
        content = self._zbuduj_opis(model, schema_cls, options)

        if options["to_stdout"]:
            self.stdout.write(content)
            return

        target = Path(self._wyjscie_dla_modelu(options["model"], options["output"]))
        self._zapisz(content, target, options["format"])

    def _generuj_wszystkie(self, options):
        """Wygeneruj compact dla wszystkich kanonicznych korzeni (rekord/autor/
        autorzy) tym samym schematem — różni je tylko model-korzeń."""
        katalog = Path(options["katalog"]) if options["katalog"] else DATA_DIR
        schema_cls = self._resolve_schema(options["schema"])
        for model_label, fname in KORZENIE.items():
            model = self._resolve_model(model_label)
            content = self._zbuduj_opis(
                model, schema_cls, {**options, "format": "compact"}
            )
            self._zapisz(content, katalog / fname, "compact")

    def _zbuduj_opis(self, model, schema_cls, options):
        """Zbuduj opis schematu (compact/json) dla danego modelu-korzenia."""
        try:
            schema = schema_cls(model)
        except Exception as e:
            raise CommandError(
                f"Nie udało się zbudować {schema_cls.__name__} dla "
                f"{model._meta.label}: {e}",
            ) from e
        fmt = options["format"]
        bundle = describe_schema_for_llm(
            schema,
            format=fmt,
            max_fk_options=options["max_fk_options"],
        )
        return self._render(
            bundle,
            fmt=fmt,
            model_label=model._meta.label,
            schema_path=options["schema"],
            indent=options["indent"],
        )

    def _wyjscie_dla_modelu(self, model_label, output):
        """Wyprowadź ścieżkę wyjścia: jawny --output wygrywa; inaczej dla
        kanonicznego korzenia użyj pliku z ``KORZENIE`` w ``DATA_DIR``."""
        if output:
            return output
        fname = KORZENIE.get(model_label)
        if fname is None:
            raise CommandError(
                f"Model {model_label!r} nie jest kanonicznym korzeniem "
                f"({', '.join(KORZENIE)}) — podaj jawnie --output.",
            )
        return str(DATA_DIR / fname)

    def _zapisz(self, content, target, fmt):
        """Zapisz artefakt z dokładnie jednym końcowym newline (idempotentne
        z end-of-file-fixer)."""
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content.rstrip("\n") + "\n", encoding="utf-8")
        except OSError as e:
            raise CommandError(f"Nie udało się zapisać {target}: {e}") from e
        self.stderr.write(
            f"Zapisano opis schematu ({fmt}, BPP {VERSION}) → {target}",
        )

    def _render(self, bundle, *, fmt, model_label, schema_path, indent):
        if fmt == "compact":
            header = "\n".join(
                (
                    f"# BPP {VERSION}",
                    f"# Model: {model_label}   Schemat: {schema_path}",
                    "# Wygenerowano: manage.py opisz_schemat_djangoql_dla_llm",
                    "# Plik generowany — nie edytuj ręcznie.",
                    "",
                    "",
                )
            )
            return header + bundle
        # json: wstrzykujemy wersję na szczyt obiektu (nagłówek # zepsułby JSON)
        payload = {"bpp_version": VERSION, **bundle}
        return json.dumps(
            payload,
            indent=indent or None,
            ensure_ascii=False,
            default=str,
        )

    def _resolve_model(self, label):
        try:
            return apps.get_model(label)
        except (LookupError, ValueError) as e:
            raise CommandError(f"Nieznany model {label!r}: {e}") from e

    def _resolve_schema(self, dotted_path):
        try:
            schema_cls = import_string(dotted_path)
        except ImportError as e:
            raise CommandError(
                f"Nie udało się zaimportować schematu {dotted_path!r}: {e}",
            ) from e
        if not (
            isinstance(schema_cls, type) and issubclass(schema_cls, DjangoQLSchema)
        ):
            raise CommandError(
                f"{dotted_path!r} nie jest podklasą DjangoQLSchema.",
            )
        return schema_cls
