# Generated migration to fix DOIorWWWMissing error classification
from django.db import migrations


def reclassify_doiorwwwmissing_errors(apps, _schema_editor):
    """
    One-time data fix to reclassify DOIorWWWMissing errors to MERYT.

    Background: DOIorWWWMissing is a subclass of WillNotExportError, which
    represents business validation errors that require user action (adding
    DOI or WWW to the publication record). The current code correctly
    classifies these as MERYTORYCZNY, but historical records have incorrect
    classification (TECH or None).

    This migration finds all DOIorWWWMissing errors and reclassifies them
    to MERYT regardless of current classification (TECH or None).
    """
    PBN_Export_Queue = apps.get_model("pbn_export_queue", "PBN_Export_Queue")

    # Find all DOIorWWWMissing errors (any classification)
    candidates = PBN_Export_Queue.objects.filter(
        komunikat__contains="DOIorWWWMissing"
    ).exclude(rodzaj_bledu="MERYT")

    count = 0
    for record in candidates:
        old_value = record.rodzaj_bledu if record.rodzaj_bledu else "None"
        print(
            f"Reclassifying DOIorWWWMissing record "
            f"ID {record.id} from {old_value} to MERYT"
        )
        record.rodzaj_bledu = "MERYT"
        record.save(update_fields=["rodzaj_bledu"])
        count += 1

    print(f"Reclassified {count} DOIorWWWMissing errors")


def reverse_reclassification(apps, _schema_editor):
    """
    Rollback: Change specific IDs back to their original state (for testing only).
    """
    PBN_Export_Queue = apps.get_model("pbn_export_queue", "PBN_Export_Queue")

    # Record ID 200 was TECH, IDs 185 and 595 were None
    # For rollback purposes, we'll set them all back to TECH
    # (None would violate NOT NULL constraint if field is required)
    candidates = PBN_Export_Queue.objects.filter(
        id__in=[185, 200, 595], rodzaj_bledu="MERYT"
    )

    for record in candidates:
        print(f"Reverting record ID {record.id} from MERYT to TECH")
        record.rodzaj_bledu = "TECH"
        record.save(update_fields=["rodzaj_bledu"])


class Migration(migrations.Migration):
    dependencies = [
        ("pbn_export_queue", "0006_reclassify_list_format_validation_errors"),
    ]

    operations = [
        migrations.RunPython(
            reclassify_doiorwwwmissing_errors,
            reverse_code=reverse_reclassification,
        ),
    ]
