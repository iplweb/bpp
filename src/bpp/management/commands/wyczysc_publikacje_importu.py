"""Reset publication records created during import testing."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.db.models import Q

from bpp.demo_data.confirm import ConfirmAborted, double_confirm
from bpp.models import (
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)


@dataclass(frozen=True)
class GenericReferenceSpec:
    model_label: str
    content_type_field: str
    object_id_field: str


@dataclass(frozen=True)
class GenericReferenceResult:
    model_label: str
    action: str
    count: int


PUBLICATION_REFERENCE_DELETES = [
    GenericReferenceSpec("bpp.Grant_Rekordu", "content_type", "object_id"),
    GenericReferenceSpec("bpp.Element_Repozytorium", "content_type", "object_id"),
    GenericReferenceSpec("bpp.Nagroda", "content_type", "object_id"),
    GenericReferenceSpec("bpp.OplatyPublikacjiLog", "content_type", "object_id"),
    GenericReferenceSpec("bpp.Publikacja_Habilitacyjna", "content_type", "object_id"),
    GenericReferenceSpec("denorm.DirtyInstance", "content_type", "object_id"),
    GenericReferenceSpec("dspace_api.SentToDSpace", "content_type", "object_id"),
    GenericReferenceSpec(
        "komparator_pbn_udzialy.BrakAutoraWPublikacji",
        "content_type",
        "object_id",
    ),
    GenericReferenceSpec(
        "pbn_api.PBNOdpowiedziNiepozadane",
        "content_type",
        "object_id",
    ),
    GenericReferenceSpec("pbn_api.SentData", "content_type", "object_id"),
    GenericReferenceSpec(
        "pbn_export_queue.PBN_Export_Queue", "content_type", "object_id"
    ),
    GenericReferenceSpec(
        "pbn_wysylka_oswiadczen.PbnWysylkaLog",
        "content_type",
        "object_id",
    ),
    GenericReferenceSpec(
        "rozbieznosci_if.IgnorujRozbieznoscIf", "content_type", "object_id"
    ),
    GenericReferenceSpec(
        "rozbieznosci_pk.IgnorujRozbieznoscPk", "content_type", "object_id"
    ),
]

PUBLICATION_REFERENCE_NULLS = [
    GenericReferenceSpec(
        "importer_publikacji.ImportSession",
        "created_record_content_type",
        "created_record_id",
    ),
    GenericReferenceSpec(
        "pbn_import.ImportedStatementInconsistency",
        "bpp_publication_content_type",
        "bpp_publication_id",
    ),
    GenericReferenceSpec(
        "zglos_publikacje.Zgloszenie_Publikacji", "content_type", "object_id"
    ),
]

PUBLICATION_DUPLICATE_CANDIDATE_SPECS = [
    GenericReferenceSpec(
        "deduplikator_publikacji.PublicationDuplicateCandidate",
        "original_content_type",
        "original_object_id",
    ),
    GenericReferenceSpec(
        "deduplikator_publikacji.PublicationDuplicateCandidate",
        "duplicate_content_type",
        "duplicate_object_id",
    ),
]

AUTHOR_REFERENCE_DELETES = [
    GenericReferenceSpec("denorm.DirtyInstance", "content_type", "object_id"),
    GenericReferenceSpec(
        "komparator_pbn_udzialy.RozbieznoscDyscyplinPBN",
        "content_type",
        "object_id",
    ),
    GenericReferenceSpec(
        "snapshot_odpiec.WartoscSnapshotu", "content_type", "object_id"
    ),
]


class Command(BaseCommand):
    help = (
        "Usuwa Wydawnictwo_Ciagle i/lub Wydawnictwo_Zwarte z pod-rekordami. "
        "Domyslnie czysci oba typy. Do uruchomien nieinteraktywnych wymagane "
        "jest --yes-i-am-sure --confirm-db <nazwa_bazy>."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--ciagle",
            action="store_true",
            help="Czysc tylko Wydawnictwo_Ciagle.",
        )
        parser.add_argument(
            "--zwarte",
            action="store_true",
            help="Czysc tylko Wydawnictwo_Zwarte.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Pokaz plan czyszczenia bez kasowania danych i bez promptow.",
        )
        parser.add_argument("--yes-i-am-sure", action="store_true")
        parser.add_argument("--confirm-db", type=str, default=None)

    def handle(self, *args, **options):
        selected = self._selected_publication_models(options)
        publication_cts = [
            ContentType.objects.get_for_model(model) for model in selected
        ]
        author_cts = self._author_content_types(selected)
        db_name = connection.settings_dict["NAME"]
        plan_text = self._plan_text(selected, publication_cts, author_cts, db_name)

        if options["dry_run"]:
            self.stdout.write(plan_text)
            self.stdout.write("\n[DRY-RUN] Nic nie skasowano.")
            return

        if options["yes_i_am_sure"]:
            self.stdout.write(plan_text)

        try:
            double_confirm(
                stdin=sys.stdin,
                stdout=self.stdout,
                database=db_name,
                plan_text=plan_text,
                yes_flag=options["yes_i_am_sure"],
                confirm_db_flag=options["confirm_db"],
            )
        except ConfirmAborted as exc:
            self.stdout.write(f"[ABORT] {exc}")
            raise SystemExit(1) from None

        with transaction.atomic():
            cleanup_results = []
            cleanup_results.extend(
                self._delete_generic_references(
                    AUTHOR_REFERENCE_DELETES,
                    author_cts,
                )
            )
            cleanup_results.extend(
                self._delete_generic_references(
                    PUBLICATION_REFERENCE_DELETES,
                    publication_cts,
                )
            )
            cleanup_results.extend(
                self._delete_generic_references(
                    PUBLICATION_DUPLICATE_CANDIDATE_SPECS,
                    publication_cts,
                )
            )
            cleanup_results.extend(
                self._null_generic_references(
                    PUBLICATION_REFERENCE_NULLS,
                    publication_cts,
                )
            )
            deleted = self._delete_publications(selected)

        self._print_cleanup_results(cleanup_results)
        self.stdout.write("\nUsunieto przez kaskady Django:")
        for model_label, count in sorted(deleted.items()):
            self.stdout.write(f"  - {model_label}: {count}")
        self.stdout.write("\n[OK] Czyszczenie publikacji zakonczone.")

    def _selected_publication_models(self, options):
        if options["ciagle"] or options["zwarte"]:
            selected = []
            if options["ciagle"]:
                selected.append(Wydawnictwo_Ciagle)
            if options["zwarte"]:
                selected.append(Wydawnictwo_Zwarte)
            return selected

        return [Wydawnictwo_Ciagle, Wydawnictwo_Zwarte]

    def _author_content_types(self, publication_models):
        publication_to_author = {
            Wydawnictwo_Ciagle: Wydawnictwo_Ciagle_Autor,
            Wydawnictwo_Zwarte: Wydawnictwo_Zwarte_Autor,
        }
        return [
            ContentType.objects.get_for_model(publication_to_author[model])
            for model in publication_models
        ]

    def _plan_text(self, publication_models, publication_cts, author_cts, db_name):
        lines = [f"Plan czyszczenia bazy '{db_name}':"]

        for model in publication_models:
            lines.append(f"  - {model._meta.label}: {model.objects.count()} rekordow")

        author_counts = self._author_counts(publication_models)
        for model_label, count in author_counts:
            lines.append(f"  - {model_label}: {count} powiazan autorow")

        related_count = 0
        related_count += self._count_generic_references(
            AUTHOR_REFERENCE_DELETES,
            author_cts,
        )
        related_count += self._count_generic_references(
            PUBLICATION_REFERENCE_DELETES,
            publication_cts,
        )
        related_count += self._count_generic_references(
            PUBLICATION_DUPLICATE_CANDIDATE_SPECS,
            publication_cts,
        )
        related_count += self._count_generic_references(
            PUBLICATION_REFERENCE_NULLS,
            publication_cts,
        )
        lines.append(f"  - generyczne referencje/logi: {related_count} rekordow")

        return "\n".join(lines)

    def _author_counts(self, publication_models):
        publication_to_author = {
            Wydawnictwo_Ciagle: Wydawnictwo_Ciagle_Autor,
            Wydawnictwo_Zwarte: Wydawnictwo_Zwarte_Autor,
        }
        return [
            (
                publication_to_author[model]._meta.label,
                publication_to_author[model].objects.count(),
            )
            for model in publication_models
        ]

    def _delete_publications(self, publication_models):
        deleted = {}
        for model in publication_models:
            _, details = model.objects.all().delete()
            for model_label, count in details.items():
                deleted[model_label] = deleted.get(model_label, 0) + count
        return deleted

    def _count_generic_references(self, specs, content_types):
        count = 0
        for model, query in self._grouped_reference_queries(specs, content_types):
            count += model.objects.filter(query).count()
        return count

    def _delete_generic_references(self, specs, content_types):
        results = []
        for model, query in self._grouped_reference_queries(specs, content_types):
            count, _ = model.objects.filter(query).delete()
            results.append(GenericReferenceResult(model._meta.label, "usunieto", count))
        return results

    def _null_generic_references(self, specs, content_types):
        results = []
        for model, query in self._grouped_reference_queries(specs, content_types):
            fields_to_null = {
                spec.content_type_field: None
                for spec in specs
                if spec.model_label == model._meta.label
            }
            fields_to_null.update(
                {
                    spec.object_id_field: None
                    for spec in specs
                    if spec.model_label == model._meta.label
                }
            )
            count = model.objects.filter(query).update(**fields_to_null)
            results.append(
                GenericReferenceResult(model._meta.label, "wyzerowano", count)
            )
        return results

    def _grouped_reference_queries(self, specs, content_types):
        queries_by_model = {}
        for spec in specs:
            model = self._get_model(spec.model_label)
            if model is None:
                continue
            query = Q(**{f"{spec.content_type_field}__in": content_types})
            query &= Q(**{f"{spec.object_id_field}__isnull": False})
            queries_by_model[model] = queries_by_model.get(model, Q()) | query

        return queries_by_model.items()

    def _get_model(self, model_label):
        app_label, model_name = model_label.split(".", 1)
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            return None

    def _print_cleanup_results(self, results):
        visible = [result for result in results if result.count]
        if not visible:
            self.stdout.write("\nBrak dodatkowych generycznych referencji.")
            return

        self.stdout.write("\nGeneryczne referencje/logi:")
        for result in sorted(visible, key=lambda item: item.model_label):
            self.stdout.write(
                f"  - {result.model_label}: {result.action} {result.count}"
            )
