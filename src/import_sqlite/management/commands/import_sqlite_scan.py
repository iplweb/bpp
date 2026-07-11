from django.core.management.base import BaseCommand

from import_sqlite.core.author_matching import aggregate_distinct
from import_sqlite.handlers.patent import parse_patent
from import_sqlite.reader import iter_records
from import_sqlite.review_io import write_authors_csv, write_patents_csv


class Command(BaseCommand):
    help = "Skanuje plik sqlite (harvester) i wypisuje CSV-e do przeglądu."

    def add_arguments(self, parser):
        parser.add_argument("sqlite_path")
        parser.add_argument("--typ", default="patent")
        parser.add_argument("--out-autorzy", default="autorzy_do_uzgodnienia.csv")
        parser.add_argument("--out-patenty", default="patenty_do_przegladu.csv")

    def handle(self, *args, **opts):
        records = list(iter_records(opts["sqlite_path"], opts["typ"]))
        patents = [parse_patent(r) for r in records]

        all_names = [name for pd in patents for name in pd.inventors]
        authors = aggregate_distinct(all_names)
        write_authors_csv(opts["out_autorzy"], authors)

        write_patents_csv(
            opts["out_patenty"],
            [
                {
                    "source_id": pd.source_id,
                    "numer_prawa": pd.numer_prawa,
                    "numer_zgloszenia": pd.numer_zgloszenia,
                    "tytul": pd.tytul,
                    "status": "DO_IMPORTU",
                    "powod": "",
                }
                for pd in patents
            ],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(patents)} patentów, {len(authors)} unikalnych twórców. "
                f"Wypełnij kolumnę 'decyzja' w {opts['out_autorzy']}."
            )
        )
