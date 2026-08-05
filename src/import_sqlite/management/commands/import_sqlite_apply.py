from denorm import denorms
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bpp.models import Autor
from import_sqlite.handlers.patent import apply_patent, build_context, parse_patent
from import_sqlite.reader import iter_records
from import_sqlite.review_io import read_authors_decisions, write_patents_csv


class Command(BaseCommand):
    help = "Importuje patenty z sqlite do BPP wg decyzji z CSV autorów."

    def add_arguments(self, parser):
        parser.add_argument("sqlite_path")
        parser.add_argument("--typ", default="patent")
        parser.add_argument("--autorzy", required=True)
        parser.add_argument("--out-patenty", default="patenty_do_przegladu.csv")
        parser.add_argument("--dry-run", action="store_true")

    def _validate_pks(self, decisions):
        """Waliduj decyzje PRZED transakcją: pk musi istnieć, wartość musi być
        pusta / ``NOWY`` / liczba."""
        zle = [v for v in decisions.values() if v and v != "NOWY" and not v.isdigit()]
        if zle:
            raise CommandError(f"nieprawidłowe wartości 'decyzja': {zle}")

        pks = {int(v) for v in decisions.values() if v.isdigit()}
        istniejace = set(Autor.objects.filter(pk__in=pks).values_list("pk", flat=True))
        brakujace = pks - istniejace
        if brakujace:
            raise CommandError(
                f"decyzja wskazuje nieistniejące pk Autora: {sorted(brakujace)}"
            )

    def handle(self, *args, **opts):
        decisions = read_authors_decisions(opts["autorzy"])
        self._validate_pks(decisions)

        ctx = build_context()
        records = list(iter_records(opts["sqlite_path"], opts["typ"]))
        patents = [parse_patent(r) for r in records]

        rows = []
        counts = {}
        try:
            with transaction.atomic():
                for pd in patents:
                    status, powod = apply_patent(pd, decisions, ctx)
                    counts[status] = counts.get(status, 0) + 1
                    rows.append(
                        {
                            "source_id": pd.source_id,
                            "numer_prawa": pd.numer_prawa,
                            "numer_zgloszenia": pd.numer_zgloszenia,
                            "tytul": pd.tytul,
                            "status": status,
                            "powod": powod,
                        }
                    )
                if opts["dry_run"]:
                    transaction.set_rollback(True)
                else:
                    denorms.flush()
        finally:
            write_patents_csv(opts["out_patenty"], rows)

        prefix = "[DRY-RUN] " if opts["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(prefix + str(counts)))
