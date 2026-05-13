"""Phase 2 of the miniblog → siteblog cutover.

Copies every row from ``miniblog_article`` into ``siteblog_article`` and
then drops ``miniblog_article``. Runs as a single migration so a fresh
``manage.py migrate`` on any environment ends in a consistent state:
data preserved, legacy table gone.

The two schemas are column-compatible — both apps were generated from
the same SplitField-based ``Article`` model, and BPP's
``miniblog_article`` already carries the auto-injected
``_article_body_excerpt`` column (see baseline-sql/baseline.sql). PK
type widens ``integer`` → ``bigint`` on insert; PostgreSQL accepts
that implicitly.

The M2M ``siteblog_article_sites`` is left empty — that matches the
original miniblog semantics ("visible on all sites").
"""
from django.db import migrations


SQL_COPY_ROWS = """
INSERT INTO siteblog_article (
    id, created, modified, status, status_changed,
    title, article_body, _article_body_excerpt, published_on, slug
)
SELECT
    id, created, modified, status, status_changed,
    title, article_body, _article_body_excerpt, published_on, slug
FROM miniblog_article
ON CONFLICT (id) DO NOTHING
"""

SQL_RESYNC_SEQUENCE = """
SELECT setval(
    pg_get_serial_sequence('siteblog_article', 'id'),
    GREATEST(
        COALESCE((SELECT MAX(id) FROM siteblog_article), 1),
        1
    )
)
"""


def copy_rows(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        # SQLite/test DBs go through model-level copy so they don't need
        # the Postgres-specific ON CONFLICT / setval syntax.
        _copy_via_orm(apps)
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(SQL_COPY_ROWS)
        cursor.execute(SQL_RESYNC_SEQUENCE)


def _copy_via_orm(apps):
    Miniblog = apps.get_model("miniblog", "Article")
    Siteblog = apps.get_model("siteblog", "Article")
    existing_ids = set(Siteblog.objects.values_list("pk", flat=True))
    rows = []
    for src in Miniblog.objects.all():
        if src.pk in existing_ids:
            continue
        rows.append(
            Siteblog(
                pk=src.pk,
                created=src.created,
                modified=src.modified,
                status=src.status,
                status_changed=src.status_changed,
                title=src.title,
                article_body=src.article_body,
                _article_body_excerpt=src._article_body_excerpt,
                published_on=src.published_on,
                slug=src.slug,
            )
        )
    if rows:
        Siteblog.objects.bulk_create(rows)


def reverse_noop(apps, schema_editor):
    """No reverse: by the time someone rolls back, ``siteblog_article`` may
    have new rows that have no counterpart in ``miniblog_article``."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("miniblog", "0003_alter_article_article_body"),
        ("siteblog", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(copy_rows, reverse_noop),
        migrations.DeleteModel(name="Article"),
    ]
