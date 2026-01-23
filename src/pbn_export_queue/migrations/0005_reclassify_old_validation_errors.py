# Generated migration to fix historical data
from django.db import migrations


def reclassify_old_validation_errors(apps, _schema_editor):
    """
    One-time data fix to reclassify old validation errors from TECH to MERYT.

    Background: Before 2026-01-20, validation errors from PBN API were
    incorrectly classified as TECHNICZNY. This was fixed in the code,
    but historical records remain incorrectly classified.

    This migration reclassifies two types of errors:
    1. HttpException with validation details (7 records: IDs 2,4,9,11,19,20,25)
    2. StatementsMissing errors (3 records: IDs 234,290,298)
    """
    PBN_Export_Queue = apps.get_model("pbn_export_queue", "PBN_Export_Queue")

    # Find old HttpException errors with validation details
    http_candidates = (
        PBN_Export_Queue.objects.filter(rodzaj_bledu="TECH")
        .filter(komunikat__contains="pbn_api.exceptions.HttpException")
        .filter(komunikat__contains='"details":')
    )

    # Find old StatementsMissing errors (WillNotExportError subclass)
    statements_candidates = PBN_Export_Queue.objects.filter(
        rodzaj_bledu="TECH", komunikat__contains="StatementsMissing"
    )

    # Log and update both types
    count = 0
    for record in http_candidates:
        print(
            f"Reclassifying HttpException record ID {record.id} from TECH to MERYT"
        )
        record.rodzaj_bledu = "MERYT"
        record.save(update_fields=["rodzaj_bledu"])
        count += 1

    for record in statements_candidates:
        print(
            f"Reclassifying StatementsMissing record ID {record.id} "
            "from TECH to MERYT"
        )
        record.rodzaj_bledu = "MERYT"
        record.save(update_fields=["rodzaj_bledu"])
        count += 1

    print(f"Reclassified {count} records total")


def reverse_reclassification(apps, _schema_editor):
    """
    Rollback: Change back to TECH (for testing only).
    """
    PBN_Export_Queue = apps.get_model("pbn_export_queue", "PBN_Export_Queue")

    # Specific IDs that were changed
    # HttpException errors: 2, 4, 9, 11, 19, 20, 25
    # StatementsMissing errors: 234, 290, 298
    old_error_ids = [2, 4, 9, 11, 19, 20, 25, 234, 290, 298]
    candidates = PBN_Export_Queue.objects.filter(
        id__in=old_error_ids, rodzaj_bledu="MERYT"
    )

    for record in candidates:
        print(f"Reverting record ID {record.id} from MERYT to TECH")
        record.rodzaj_bledu = "TECH"
        record.save(update_fields=["rodzaj_bledu"])


class Migration(migrations.Migration):

    dependencies = [
        ("pbn_export_queue", "0004_add_wykluczone_field"),
    ]

    operations = [
        migrations.RunPython(
            reclassify_old_validation_errors,
            reverse_code=reverse_reclassification,
        ),
    ]
