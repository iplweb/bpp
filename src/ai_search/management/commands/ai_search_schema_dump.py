from django.core.management import BaseCommand

from ai_search import schema_export


class Command(BaseCommand):
    help = (
        "Wypisuje na stdout wygenerowany (compact) opis schematu wysyłany do "
        "LLM dla danego modelu ('rekord' lub 'autor') — przydatne do ręcznej "
        "inspekcji treści oraz do zmierzenia rozmiaru (np. `| wc -c`)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "model_key",
            choices=("rekord", "autor"),
            help="Klucz modelu danych (patrz bpp.views.zapytanie.MODELS).",
        )
        parser.add_argument(
            "--regenerate",
            action="store_true",
            help="Pomiń cache i zbuduj schemat od nowa (zapisze go też do cache).",
        )

    def handle(self, *args, **options):
        model_key = options["model_key"]
        if options["regenerate"]:
            data = schema_export.regenerate(model_key)
        else:
            data = schema_export.schema_for_llm(model_key)
        self.stdout.write(data)
        self.stderr.write(f"# {model_key}: {len(data)} znaków")
