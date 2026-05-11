"""BPP-side replacement for ``dynamic_admin_columns.0001_initial``.

* Always registers the package's models in Django's state.
* For the on-disk schema, runs idempotent ``CREATE TABLE IF NOT
  EXISTS`` so the migration is safe regardless of whether the
  ``dynamic_columns_*`` tables already exist (legacy BPP-prod or
  baseline-loaded test DB) or need to be created from scratch
  (``--create-db`` / fresh BPP install).

The companion ``bpp.0416_rename_dynamic_columns_to_admin`` migration
applies the per-user schema delta on databases that still hold the
0.1 schema.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# NOTE: ``user_id`` references ``auth_user(id)`` literally because that
# is the table name *as recorded in the upstream package's
# 0001_initial* (which the package targets generic Django projects with
# the default ``auth.User``). BPP swaps ``AUTH_USER_MODEL`` to
# ``bpp.BppUser`` (table ``bpp_bppuser``), so this CREATE block would
# fail in isolation. In practice every BPP database is bootstrapped
# from ``baseline.sql`` which already carries the
# ``dynamic_columns_*`` tables, so the ``IF NOT EXISTS`` guard turns
# the CREATE into a no-op. The companion
# ``bpp.0416_rename_dynamic_columns_to_admin`` migration adds the
# ``user_id`` FK through Django's schema editor so it resolves to the
# correct BPP-specific table.
CREATE_TABLES_SQL = r"""
CREATE TABLE IF NOT EXISTS dynamic_columns_modeladmin (
    id              bigserial PRIMARY KEY,
    class_name      text NOT NULL,
    model_ref_id    integer NOT NULL
                    REFERENCES django_content_type(id)
                    DEFERRABLE INITIALLY DEFERRED,
    user_id         integer NULL
                    REFERENCES auth_user(id)
                    ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX IF NOT EXISTS dynamic_columns_modeladmin_model_ref_idx
    ON dynamic_columns_modeladmin(model_ref_id);

CREATE TABLE IF NOT EXISTS dynamic_columns_modeladmincolumn (
    id          bigserial PRIMARY KEY,
    col_name    varchar(255) NOT NULL,
    enabled     boolean NOT NULL DEFAULT TRUE,
    ordering    smallint NOT NULL CHECK (ordering >= 0),
    parent_id   bigint NOT NULL
                REFERENCES dynamic_columns_modeladmin(id)
                ON DELETE CASCADE
                DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX IF NOT EXISTS dynamic_columns_modeladmincolumn_parent_idx
    ON dynamic_columns_modeladmincolumn(parent_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'dynamic_columns_modeladmincolumn_parent_id_col_name_key'
          AND conrelid = 'dynamic_columns_modeladmincolumn'::regclass
    ) THEN
        BEGIN
            EXECUTE 'ALTER TABLE dynamic_columns_modeladmincolumn '
                    'ADD CONSTRAINT '
                    'dynamic_columns_modeladmincolumn_parent_id_col_name_key '
                    'UNIQUE (parent_id, col_name)';
        EXCEPTION WHEN duplicate_table THEN
            -- Some pre-existing unique under a different name; skip.
            NULL;
        END;
    END IF;
END
$$;
"""


REVERSE_TABLES_SQL = r"""
DROP TABLE IF EXISTS dynamic_columns_modeladmincolumn CASCADE;
DROP TABLE IF EXISTS dynamic_columns_modeladmin CASCADE;
"""


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=CREATE_TABLES_SQL,
                    reverse_sql=REVERSE_TABLES_SQL,
                ),
            ],
            state_operations=[
                migrations.CreateModel(
                    name="ModelAdmin",
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
                        ("class_name", models.TextField()),
                        (
                            "model_ref",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                to="contenttypes.contenttype",
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                blank=True,
                                help_text=(
                                    "If set, this is a personal column "
                                    "configuration owned by that user. "
                                    "NULL rows are global defaults."
                                ),
                                null=True,
                                on_delete=django.db.models.deletion.CASCADE,
                                to=settings.AUTH_USER_MODEL,
                                verbose_name="User",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Model admin",
                        "verbose_name_plural": "Model admins",
                        "db_table": "dynamic_columns_modeladmin",
                        "ordering": ("class_name", "user_id"),
                    },
                ),
                migrations.CreateModel(
                    name="ModelAdminColumn",
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
                            "col_name",
                            models.CharField(
                                max_length=255, verbose_name="Column name"
                            ),
                        ),
                        (
                            "enabled",
                            models.BooleanField(default=True, verbose_name="Enabled"),
                        ),
                        (
                            "ordering",
                            models.PositiveSmallIntegerField(verbose_name="Ordering"),
                        ),
                        (
                            "parent",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                to="dynamic_admin_columns.modeladmin",
                                verbose_name="Parent",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Model admin column",
                        "verbose_name_plural": "Model admin columns",
                        "db_table": "dynamic_columns_modeladmincolumn",
                        "ordering": ("parent", "ordering"),
                    },
                ),
                migrations.AddConstraint(
                    model_name="modeladmin",
                    constraint=models.UniqueConstraint(
                        condition=models.Q(("user__isnull", True)),
                        fields=("class_name", "model_ref"),
                        name="dyncol_unique_global_modeladmin",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="modeladmin",
                    constraint=models.UniqueConstraint(
                        condition=models.Q(("user__isnull", False)),
                        fields=("user", "class_name", "model_ref"),
                        name="dyncol_unique_user_modeladmin",
                    ),
                ),
                migrations.AlterUniqueTogether(
                    name="modeladmincolumn",
                    unique_together={("parent", "col_name")},
                ),
            ],
        ),
    ]
