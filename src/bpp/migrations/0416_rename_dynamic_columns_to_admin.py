"""Schema delta for the externalised ``dynamic_admin_columns`` package.

Applies the per-user schema delta on a BPP database that still holds
the legacy 0.1 schema (no ``user_id`` column on
``dynamic_columns_modeladmin``). Fresh or already-upgraded databases
hit a no-op short-circuit at the top of :func:`apply_upgrade`.

We add the ``user_id`` column through Django's schema editor so the
foreign key correctly references whatever ``AUTH_USER_MODEL`` is
configured for the project (``bpp.BppUser`` in BPP — table
``bpp_bppuser``) rather than hard-coding ``auth_user``.
"""

from django.apps import apps as django_apps
from django.db import migrations


def apply_upgrade(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
              FROM information_schema.columns
             WHERE table_schema = current_schema()
               AND table_name = 'dynamic_columns_modeladmin'
               AND column_name = 'user_id'
            """
        )
        if cursor.fetchone() is not None:
            return  # already upgraded

        cursor.execute(
            """
            SELECT 1
              FROM information_schema.tables
             WHERE table_schema = current_schema()
               AND table_name = 'dynamic_columns_modeladmin'
            """
        )
        if cursor.fetchone() is None:
            return  # fresh install, package's initial will create the table

    # Add ``user_id`` through the model registry so the FK target
    # resolves through ``settings.AUTH_USER_MODEL``.
    ModelAdmin = apps.get_model("dynamic_admin_columns", "ModelAdmin")
    user_field = ModelAdmin._meta.get_field("user")
    schema_editor.add_field(ModelAdmin, user_field)

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT conname
              FROM pg_constraint
             WHERE conrelid = 'dynamic_columns_modeladmin'::regclass
               AND contype = 'u'
               AND conname NOT IN (
                   'dyncol_unique_global_modeladmin',
                   'dyncol_unique_user_modeladmin'
               )
            """
        )
        for (legacy_name,) in cursor.fetchall():
            cursor.execute(
                f'ALTER TABLE dynamic_columns_modeladmin '
                f'DROP CONSTRAINT IF EXISTS "{legacy_name}"'
            )

    # Install the two conditional uniques through the schema editor so
    # the model state and the database stay in sync.
    for constraint_name in (
        "dyncol_unique_global_modeladmin",
        "dyncol_unique_user_modeladmin",
    ):
        constraint = next(
            c for c in ModelAdmin._meta.constraints if c.name == constraint_name
        )
        # Ignore constraint already existing on fresh-but-rehydrated DBs.
        try:
            schema_editor.add_constraint(ModelAdmin, constraint)
        except Exception:
            pass

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM django_migrations WHERE app = 'dynamic_columns'"
        )


def reverse_upgrade(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    ModelAdmin = apps.get_model("dynamic_admin_columns", "ModelAdmin")

    for constraint_name in (
        "dyncol_unique_global_modeladmin",
        "dyncol_unique_user_modeladmin",
    ):
        try:
            constraint = next(
                c for c in ModelAdmin._meta.constraints if c.name == constraint_name
            )
            schema_editor.remove_constraint(ModelAdmin, constraint)
        except (StopIteration, Exception):
            pass

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
              FROM information_schema.columns
             WHERE table_name = 'dynamic_columns_modeladmin'
               AND column_name = 'user_id'
            """
        )
        if cursor.fetchone() is None:
            return

    user_field = ModelAdmin._meta.get_field("user")
    schema_editor.remove_field(ModelAdmin, user_field)

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            ALTER TABLE dynamic_columns_modeladmin
                ADD CONSTRAINT
                    dynamic_columns_modeladmin_class_name_model_ref_id_key
                    UNIQUE (class_name, model_ref_id)
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0415_merge_20260504_0907"),
        ("dynamic_admin_columns", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(apply_upgrade, reverse_code=reverse_upgrade),
    ]
