"""
Management command to globally remap Jednostka in related records.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from bpp.models import (
    Autor_Jednostka,
    Jednostka,
    Patent_Autor,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)


class Command(BaseCommand):
    help = (
        "Globally remap one Jednostka to another in all related records. "
        "Handles Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, "
        "Patent_Autor, and Autor_Jednostka. "
        "Includes dry-run mode and conflict detection for Autor_Jednostka.\n\n"
        "Usage examples:\n"
        "  # Using slugs:\n"
        "  python manage.py remap_jednostka katedra-informatyki instytut-informatyki\n"
        "  # Using IDs:\n"
        "  python manage.py remap_jednostka 123 456\n"
        "  # Mixed usage:\n"
        "  python manage.py remap_jednostka katedra-informatyki 456\n\n"
        "  # Dry run to see what would be changed:\n"
        "  python manage.py remap_jednostka katedra-informatyki instytut-informatyki --dry-run\n"
        "  # Run without confirmation prompt:\n"
        "  python manage.py remap_jednostka katedra-informatyki instytut-informatyki --no-confirm"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "source_jednostka",
            type=str,
            help="Slug or ID of the source Jednostka to remap FROM",
        )
        parser.add_argument(
            "target_jednostka",
            type=str,
            help="Slug or ID of the target Jednostka to remap TO",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without actually making changes",
        )
        parser.add_argument(
            "--no-confirm",
            action="store_true",
            help="Skip confirmation prompt before applying changes",
        )

    def get_jednostka_by_slug_or_id(self, identifier):
        """
        Get Jednostka instance by slug or ID.

        Args:
            identifier: Slug (string) or ID (int or string representing int)

        Returns:
            Jednostka instance

        Raises:
            CommandError: If Jednostka not found
        """
        try:
            # Try to parse as integer ID first
            jednostka_id = int(identifier)
            try:
                return Jednostka.objects.get(pk=jednostka_id)
            except Jednostka.DoesNotExist:
                raise CommandError(f"Jednostka with ID {jednostka_id} does not exist")
        except ValueError:
            # Not an integer, treat as slug
            try:
                return Jednostka.objects.get(slug=identifier)
            except Jednostka.DoesNotExist:
                raise CommandError(f"Jednostka with slug '{identifier}' does not exist")

    def get_model_info(self):
        """Get information about models that have Jednostka references."""
        return [
            {
                "model": Autor_Jednostka,
                "name": "Autor_Jednostka",
                "field": "jednostka",
                "has_conflicts": True,
            },
            {
                "model": Wydawnictwo_Ciagle_Autor,
                "name": "Wydawnictwo_Ciagle_Autor",
                "field": "jednostka",
                "has_conflicts": False,
            },
            {
                "model": Wydawnictwo_Zwarte_Autor,
                "name": "Wydawnictwo_Zwarte_Autor",
                "field": "jednostka",
                "has_conflicts": False,
            },
            {
                "model": Patent_Autor,
                "name": "Patent_Autor",
                "field": "jednostka",
                "has_conflicts": False,
            },
        ]

    def find_potential_conflicts(self, source_jednostka, target_jednostka):
        """Find potential Autor_Jednostka conflicts after remapping."""
        conflicts = []

        # Get all autor-jednostka combinations for source
        source_records = Autor_Jednostka.objects.filter(jednostka=source_jednostka)

        for record in source_records:
            # Build query conditions carefully to handle None values
            base_q = Q(autor=record.autor, jednostka=target_jednostka)

            # Check if similar record already exists for target
            if record.rozpoczal_prace is not None:
                existing_q = base_q & Q(rozpoczal_prace=record.rozpoczal_prace)
            else:
                existing_q = base_q & Q(rozpoczal_prace__isnull=True)

            existing = Autor_Jednostka.objects.filter(existing_q).first()

            if existing:
                conflicts.append(
                    {
                        "autor": record.autor,
                        "source": record,
                        "target": existing,
                        "type": "identical_period",
                    }
                )
                continue

            # Check for overlapping periods
            overlapping_conditions = []

            # Case 1: target period starts before source starts and ends after source starts
            if record.rozpoczal_prace is not None:
                overlapping_conditions.append(
                    Q(rozpoczal_prace__lte=record.rozpoczal_prace)
                    & Q(zakonczyl_prace__gte=record.rozpoczal_prace)
                )

            # Case 2: target period starts before source ends and ends after source ends
            if record.zakonczyl_prace is not None:
                overlapping_conditions.append(
                    Q(rozpoczal_prace__lte=record.zakonczyl_prace)
                    & Q(zakonczyl_prace__gte=record.zakonczyl_prace)
                )

            # Case 3: target has no start date (open-ended)
            overlapping_conditions.append(Q(rozpoczal_prace__isnull=True))

            # Case 4: target starts before source starts and has no end date
            if record.rozpoczal_prace is not None:
                overlapping_conditions.append(
                    Q(rozpoczal_prace__lte=record.rozpoczal_prace)
                    & Q(zakonczyl_prace__isnull=True)
                )

            # Combine all conditions with OR
            overlapping_q = base_q
            for condition in overlapping_conditions:
                overlapping_q = overlapping_q | (base_q & condition)

            overlapping = Autor_Jednostka.objects.filter(overlapping_q).first()

            if overlapping:
                conflicts.append(
                    {
                        "autor": record.autor,
                        "source": record,
                        "target": overlapping,
                        "type": "overlapping_period",
                    }
                )

        return conflicts

    def handle(self, *args, **options):
        source_jednostka_identifier = options["source_jednostka"]
        target_jednostka_identifier = options["target_jednostka"]
        dry_run = options["dry_run"]
        no_confirm = options["no_confirm"]

        # Validate that identifiers are different
        if source_jednostka_identifier == target_jednostka_identifier:
            raise CommandError(
                "Source and target Jednostka identifiers must be different"
            )

        # Get Jednostka instances
        source_jednostka = self.get_jednostka_by_slug_or_id(source_jednostka_identifier)
        target_jednostka = self.get_jednostka_by_slug_or_id(target_jednostka_identifier)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nRemapping Jednostka '{source_jednostka.nazwa}' "
                f"(ID: {source_jednostka.pk}) "
                f"to '{target_jednostka.nazwa}' (ID: {target_jednostka.pk})"
            )
        )

        # Get counts for all affected models
        total_count = 0
        model_info = self.get_model_info()

        self.stdout.write("\nRecords that will be affected:")
        for info in model_info:
            count = info["model"].objects.filter(jednostka=source_jednostka).count()
            if count > 0:
                self.stdout.write(f"  {info['name']}: {count} records")
                total_count += count
            else:
                self.stdout.write(f"  {info['name']}: no records")

        if total_count == 0:
            self.stdout.write(
                self.style.WARNING("\nNo records found for source Jednostka.")
            )
            return

        # Check for conflicts in Autor_Jednostka
        conflicts = self.find_potential_conflicts(source_jednostka, target_jednostka)

        if conflicts:
            self.stdout.write(
                self.style.WARNING(f"\nFound {len(conflicts)} potential conflicts:")
            )
            for conflict in conflicts:
                if conflict["type"] == "identical_period":
                    self.stdout.write(
                        f"  - Autor '{conflict['autor']}' already has identical period "
                        f"in target Jednostka (ID: {conflict['target'].pk})"
                    )
                else:
                    self.stdout.write(
                        f"  - Autor '{conflict['autor']}' has overlapping period "
                        f"in target Jednostka (ID: {conflict['target'].pk})"
                    )

        # Show what will be changed
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS("\n[DRY RUN] No changes will be made.")
            )
            self.stdout.write(
                "Run with --no-confirm to apply changes or without --dry-run to confirm."
            )
            return

        # Confirmation prompt
        if not no_confirm:
            self.stdout.write(
                "\nThis operation will permanently remap the Jednostka references."
            )
            if conflicts:
                message = (
                    "WARNING: Conflicts detected. Some Autor_Jednostka records may be "
                    "skipped or require manual intervention."
                )
                self.stdout.write(self.style.WARNING(message))

            confirm = input("\nAre you sure you want to proceed? (yes/no): ")
            if confirm.lower() != "yes":
                self.stdout.write(self.style.ERROR("Operation cancelled."))
                return

        # Perform the remapping
        self.stdout.write("\nStarting remapping...")
        total_updated = 0
        skipped = 0

        with transaction.atomic():
            for info in model_info:
                model = info["model"]
                field_name = info["field"]
                has_conflicts = info["has_conflicts"]

                queryset = model.objects.filter(jednostka=source_jednostka)
                count = queryset.count()

                if count == 0:
                    continue

                if has_conflicts:
                    # Handle Autor_Jednostka with conflict detection
                    updated = 0
                    for record in queryset:
                        # Check if this specific record would conflict
                        conflict_for_record = any(
                            c for c in conflicts if c["source"].pk == record.pk
                        )

                        if conflict_for_record:
                            message = (
                                f"  Skipping {model.__name__} ID {record.pk} for autor "
                                f"'{record.autor}' - conflict detected"
                            )
                            self.stdout.write(self.style.WARNING(message))
                            skipped += 1
                            continue

                        # Safe to update
                        setattr(record, field_name, target_jednostka)
                        record.save()
                        updated += 1

                    total_updated += updated
                    if updated > 0:
                        message = (
                            f"  {model.__name__}: updated {updated} records "
                            f"(skipped {count - updated} due to conflicts)"
                        )
                        self.stdout.write(self.style.SUCCESS(message))
                else:
                    # Direct update for other models
                    updated = queryset.update(**{field_name: target_jednostka})
                    total_updated += updated
                    if updated > 0:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  {model.__name__}: updated {updated} records"
                            )
                        )

        # Final summary
        self.stdout.write(self.style.SUCCESS("\nRemapping complete!"))
        self.stdout.write(f"  Total records updated: {total_updated}")
        if skipped > 0:
            self.stdout.write(
                self.style.WARNING(f"  Records skipped due to conflicts: {skipped}")
            )
            self.stdout.write(
                "\nPlease review and manually resolve the conflicts listed above."
            )

        # Check if source Jednostka can be safely deleted
        remaining_references = 0
        for info in model_info:
            remaining_references += (
                info["model"].objects.filter(jednostka=source_jednostka).count()
            )

        if remaining_references == 0:
            message = (
                f"\nSource Jednostka '{source_jednostka.nazwa}' has no more references "
                "and can be safely deleted if needed."
            )
            self.stdout.write(self.style.SUCCESS(message))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"\nSource Jednostka '{source_jednostka.nazwa}' still has "
                    f"{remaining_references} references and cannot be deleted yet."
                )
            )
