from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("deduplikator_autorow", "0010_add_ignored_author"),
    ]

    operations = [
        migrations.AlterField(
            model_name="duplicatescanrun",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Oczekuje"),
                    ("running", "W trakcie"),
                    ("completed", "Zakończone"),
                    (
                        "partial_completed",
                        "Częściowo zakończone (faza PBN OK, general anulowana)",
                    ),
                    ("cancelled", "Anulowane"),
                    ("failed", "Błąd"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
                verbose_name="Status",
            ),
        ),
        migrations.AddField(
            model_name="duplicatescanrun",
            name="phase",
            field=models.CharField(
                blank=True,
                choices=[("pbn", "Faza PBN"), ("general", "Faza ogólna")],
                max_length=20,
                verbose_name="Aktualna faza",
            ),
        ),
        migrations.AddField(
            model_name="duplicatecandidate",
            name="scan_mode",
            field=models.CharField(
                choices=[("pbn", "PBN"), ("general", "Ogólny")],
                db_index=True,
                default="pbn",
                max_length=20,
                verbose_name="Tryb skanowania",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="duplicatecandidate",
            name="unique_scan_main_duplicate",
        ),
        migrations.AddIndex(
            model_name="duplicatecandidate",
            index=models.Index(
                fields=["scan_run", "scan_mode", "status"],
                name="deduplikato_scan_ru_78ad22_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="duplicatecandidate",
            constraint=models.UniqueConstraint(
                fields=("scan_run", "scan_mode", "main_autor", "duplicate_autor"),
                name="unique_scan_mode_main_duplicate",
            ),
        ),
    ]
