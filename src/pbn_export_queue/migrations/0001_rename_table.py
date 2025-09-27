# Generated manually to rename existing table and preserve data

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        (
            "pbn_api",
            "0060_alter_osobazinstytucji_personid",
        ),  # Last migration where the table still exists
    ]

    operations = [
        migrations.RunSQL(
            # Rename the existing table from pbn_api to pbn_export_queue
            sql="ALTER TABLE IF EXISTS pbn_api_pbn_export_queue RENAME TO pbn_export_queue_pbn_export_queue;",
            reverse_sql="ALTER TABLE IF EXISTS pbn_export_queue_pbn_export_queue RENAME TO pbn_api_pbn_export_queue;",
        ),
    ]
