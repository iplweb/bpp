from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte


class Command(BaseCommand):
    help = "Find and optionally fix HTML entities (&lt; and &gt;) in tytul_oryginalny field"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            dest="fix",
            default=False,
            help="Apply fixes to replace &lt; with < and &gt; with >",
        )
        parser.add_argument(
            "--limit",
            type=int,
            dest="limit",
            default=None,
            help="Limit the number of records to process",
        )

    def process_model(self, model_class, fix_mode, limit=None):
        """Process a single model type for HTML entities"""
        model_name = model_class.__name__

        # Find records with HTML entities
        records_with_lt = model_class.objects.filter(tytul_oryginalny__icontains="&lt;")
        records_with_gt = model_class.objects.filter(tytul_oryginalny__icontains="&gt;")

        # Get unique records that have either entity
        all_records = (records_with_lt | records_with_gt).distinct()

        if limit:
            all_records = all_records[:limit]

        total_count = all_records.count()

        if total_count == 0:
            return 0, 0

        self.stdout.write(
            self.style.WARNING(
                f"\n{model_name}: Found {total_count} records with HTML entities"
            )
        )

        # Show some examples
        self.stdout.write(f"Examples from {model_name}:")
        for i, record in enumerate(all_records[:3]):
            self.stdout.write(f"  {i+1}. {record.tytul_oryginalny[:80]}...")

        if total_count > 3:
            self.stdout.write(f"  ... and {total_count - 3} more records")

        if not fix_mode:
            return total_count, 0

        # Apply fixes
        updated_count = 0
        with transaction.atomic():
            for record in all_records:
                original_tytul_oryginalny = record.tytul_oryginalny
                original_tytul = record.tytul

                # Replace HTML entities in both fields
                record.tytul_oryginalny = record.tytul_oryginalny.replace(
                    "&lt;", "<"
                ).replace("&gt;", ">")
                if record.tytul:
                    record.tytul = record.tytul.replace("&lt;", "<").replace(
                        "&gt;", ">"
                    )

                # Only save if something changed
                if (
                    record.tytul_oryginalny != original_tytul_oryginalny
                    or record.tytul != original_tytul
                ):
                    record.save()
                    updated_count += 1

                    if updated_count <= 2:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✓ Updated: {original_tytul_oryginalny[:50]}..."
                            )
                        )
                        self.stdout.write(f"    → {record.tytul_oryginalny[:50]}...")

        return total_count, updated_count

    def handle(self, *args, **options):
        fix_mode = options.get("fix", False)
        limit = options.get("limit", None)

        total_found = 0
        total_updated = 0

        # Process both model types
        for model_class in [Wydawnictwo_Ciagle, Wydawnictwo_Zwarte]:
            found, updated = self.process_model(model_class, fix_mode, limit)
            total_found += found
            total_updated += updated

        if total_found == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "\nNo records found with &lt; or &gt; entities in any model."
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f"\nTotal: {total_found} records found with HTML entities"
            )
        )

        if not fix_mode:
            self.stdout.write(
                self.style.WARNING(
                    "\nTo fix these records, run the command with --fix option:\n"
                    "python src/manage.py fix_html_entities --fix"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully updated {total_updated} records total."
                )
            )
