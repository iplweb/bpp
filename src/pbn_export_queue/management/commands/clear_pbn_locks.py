"""
Management command to clear all PBN export locks from Redis.
Use with caution - only for emergency situations.
"""

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError

from pbn_export_queue.tasks import LOCK_PREFIX


class Command(BaseCommand):
    help = "Clear all PBN export locks from Redis (emergency use only)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force clear without confirmation",
        )
        parser.add_argument(
            "--pk",
            type=int,
            help="Clear lock for specific PBN Export Queue ID only",
        )

    def handle(self, *args, **options):
        if options["pk"]:
            # Clear specific lock
            lock_key = f"{LOCK_PREFIX}{options['pk']}"
            if cache.get(lock_key):
                cache.delete(lock_key)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Cleared lock for PBN Export Queue ID: {options['pk']}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"No lock found for PBN Export Queue ID: {options['pk']}"
                    )
                )
            return

        # Clear all locks - requires confirmation
        if not options["force"]:
            self.stdout.write(
                self.style.WARNING("This will clear ALL PBN export locks from Redis!")
            )
            self.stdout.write(
                self.style.WARNING("This should only be used in emergency situations.")
            )
            confirm = input("Are you sure? Type 'yes' to continue: ")
            if confirm.lower() != "yes":
                raise CommandError("Operation cancelled")

        # Count existing locks before clearing
        count = 0
        # Since we can't directly pattern match with Django cache,
        # we'll check known queue items
        from pbn_export_queue.models import PBN_Export_Queue

        # Get all potential queue items
        queue_items = PBN_Export_Queue.objects.filter(
            wysylke_zakonczono=None
        ).values_list("pk", flat=True)

        for pk in queue_items:
            lock_key = f"{LOCK_PREFIX}{pk}"
            if cache.get(lock_key):
                cache.delete(lock_key)
                count += 1

        if count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully cleared {count} PBN export locks")
            )
        else:
            self.stdout.write(self.style.WARNING("No PBN export locks found to clear"))

        # Additional cleanup - try to clear any orphaned locks
        # This is a best effort attempt for locks that might exist
        # for deleted queue items
        self.stdout.write("Checking for orphaned locks...")

        # Check a reasonable range of IDs for orphaned locks
        # (this is a safety measure in case of database inconsistency)
        orphaned_count = 0
        max_id = PBN_Export_Queue.objects.all().order_by("-pk").first()
        if max_id:
            for pk in range(1, max_id.pk + 100):  # Check up to 100 IDs beyond max
                if pk not in queue_items:
                    lock_key = f"{LOCK_PREFIX}{pk}"
                    if cache.get(lock_key):
                        cache.delete(lock_key)
                        orphaned_count += 1

        if orphaned_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"Cleared {orphaned_count} orphaned locks")
            )
