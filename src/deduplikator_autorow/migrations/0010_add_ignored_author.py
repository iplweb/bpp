import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def rename_leftover_ignoredauthor_indexes(apps, schema_editor):
    """Rename indexes that PostgreSQL kept after RenameModel in 0009.

    Migration 0009 renamed the IgnoredAuthor model to IgnoredScientist, which
    in PostgreSQL renames the table but keeps existing index names. Those
    `deduplikator_autorow_ignoredauthor_*` index names would collide with
    auto-generated names for the new IgnoredAuthor model created here.

    We rename them to match the new (IgnoredScientist) table to avoid the
    collision and keep names consistent with the actual table. SQL is
    idempotent (uses IF EXISTS) so it works against fresh DBs too.
    """
    renames = [
        (
            "deduplikator_autorow_ignoredauthor_autor_id_5e237500",
            "deduplikator_autorow_ignoredsci_autor_id_5e237500",
        ),
        (
            "deduplikator_autorow_ignoredauthor_created_by_id_3d0a197e",
            "deduplikator_autorow_ignoredsci_created_by_id_3d0a197e",
        ),
        (
            "deduplikator_autorow_ignoredauthor_scientist_id_ae6083d3_like",
            "deduplikator_autorow_ignoredsci_scientist_id_ae6083d3_like",
        ),
        (
            "deduplikator_autorow_ignoredauthor_pkey",
            "deduplikator_autorow_ignoredscientist_pkey",
        ),
        (
            "deduplikator_autorow_ignoredauthor_scientist_id_key",
            "deduplikator_autorow_ignoredscientist_scientist_id_key",
        ),
    ]
    with schema_editor.connection.cursor() as cursor:
        for old_name, new_name in renames:
            cursor.execute(
                f'ALTER INDEX IF EXISTS "{old_name}" RENAME TO "{new_name}"'
            )


def reverse_rename_leftover_ignoredauthor_indexes(apps, schema_editor):
    renames = [
        (
            "deduplikator_autorow_ignoredsci_autor_id_5e237500",
            "deduplikator_autorow_ignoredauthor_autor_id_5e237500",
        ),
        (
            "deduplikator_autorow_ignoredsci_created_by_id_3d0a197e",
            "deduplikator_autorow_ignoredauthor_created_by_id_3d0a197e",
        ),
        (
            "deduplikator_autorow_ignoredsci_scientist_id_ae6083d3_like",
            "deduplikator_autorow_ignoredauthor_scientist_id_ae6083d3_like",
        ),
        (
            "deduplikator_autorow_ignoredscientist_pkey",
            "deduplikator_autorow_ignoredauthor_pkey",
        ),
        (
            "deduplikator_autorow_ignoredscientist_scientist_id_key",
            "deduplikator_autorow_ignoredauthor_scientist_id_key",
        ),
    ]
    with schema_editor.connection.cursor() as cursor:
        for old_name, new_name in renames:
            cursor.execute(
                f'ALTER INDEX IF EXISTS "{old_name}" RENAME TO "{new_name}"'
            )


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0413_bppuser_autor_onetoone"),
        ("deduplikator_autorow", "0009_rename_ignoredauthor_ignoredscientist"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            rename_leftover_ignoredauthor_indexes,
            reverse_rename_leftover_ignoredauthor_indexes,
        ),
        migrations.CreateModel(
            name="IgnoredAuthor",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "reason",
                    models.CharField(
                        blank=True,
                        max_length=500,
                        verbose_name="Powód ignorowania",
                    ),
                ),
                (
                    "created_on",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        verbose_name="Data utworzenia",
                    ),
                ),
                (
                    "autor",
                    models.OneToOneField(
                        help_text="Autor BPP do ignorowania w deduplikacji ogólnej",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="bpp.autor",
                        verbose_name="Autor (BPP)",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Utworzył",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ignorowany autor (BPP)",
                "verbose_name_plural": "Ignorowani autorzy (BPP)",
                "ordering": ["-created_on"],
            },
        ),
    ]
