# Generated migration to fix list-format validation errors
from django.db import migrations


def reclassify_list_format_errors(apps, _schema_editor):
    """
    One-time data fix to reclassify list-format validation errors from TECH to MERYT.

    Background: Migration 0005 reclassified validation errors with "details" field
    (Format 1), but missed validation errors in list format (Format 2) which have
    "code" but no "details".

    Example list format:
    [{"requestPosition":0,"code":"NOT_UNIQUE_PUBLICATION_ISBN_ISMN",
      "description":"Publikacja o identycznym ISBN..."}]

    This migration finds HttpException errors with "code" but without "details"
    and reclassifies them from TECH to MERYT.
    """
    PBN_Export_Queue = apps.get_model("pbn_export_queue", "PBN_Export_Queue")

    # Find old HttpException errors in list format (with "code" but no "details")
    list_format_candidates = (
        PBN_Export_Queue.objects.filter(rodzaj_bledu="TECH")
        .filter(komunikat__contains="pbn_api.exceptions.HttpException")
        .filter(komunikat__contains='"code":')
        .exclude(komunikat__contains='"details":')
    )

    count = 0
    for record in list_format_candidates:
        print(
            f"Reclassifying list-format HttpException record "
            f"ID {record.id} from TECH to MERYT"
        )
        record.rodzaj_bledu = "MERYT"
        record.save(update_fields=["rodzaj_bledu"])
        count += 1

    print(f"Reclassified {count} list-format validation errors")


def reverse_reclassification(apps, _schema_editor):
    """
    Rollback: Change ID 880 back to TECH (for testing only).
    """
    PBN_Export_Queue = apps.get_model("pbn_export_queue", "PBN_Export_Queue")

    # Specific ID that should be changed
    candidates = PBN_Export_Queue.objects.filter(id=880, rodzaj_bledu="MERYT")

    for record in candidates:
        print(f"Reverting record ID {record.id} from MERYT to TECH")
        record.rodzaj_bledu = "TECH"
        record.save(update_fields=["rodzaj_bledu"])


class Migration(migrations.Migration):
    dependencies = [
        ("pbn_export_queue", "0005_reclassify_old_validation_errors"),
    ]

    operations = [
        migrations.RunPython(
            reclassify_list_format_errors,
            reverse_code=reverse_reclassification,
        ),
    ]
