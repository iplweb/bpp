"""Copy Article rows from legacy ``miniblog`` to ``siteblog``.

Dual-stack migration helper: ``miniblog`` and ``siteblog`` co-exist, the
``miniblog_article`` table stays as a read-only fallback, and this command
materializes its content into ``siteblog_article``.

Idempotent: rows whose ``pk`` already exists in the target are skipped (use
``--truncate-target`` to start fresh). M2M ``sites`` is left empty on the
target — that matches siteblog's "visible everywhere" semantics, which is
the original miniblog behaviour.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from miniblog.models import Article as MiniblogArticle
from siteblog.models import Article as SiteblogArticle


class Command(BaseCommand):
    help = "Copy miniblog.Article rows into siteblog.Article (dual-stack)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report counts without writing to siteblog_article.",
        )
        parser.add_argument(
            "--truncate-target",
            action="store_true",
            help=(
                "DELETE FROM siteblog_article before copy. Use only if you "
                "are re-running the migration after a failed attempt."
            ),
        )

    def handle(self, *, dry_run, truncate_target, **options):
        source_qs = MiniblogArticle.objects.all().order_by("pk")
        source_count = source_qs.count()
        existing_target_ids = set(
            SiteblogArticle.objects.values_list("pk", flat=True)
        )

        self.stdout.write(
            f"miniblog_article rows:  {source_count}\n"
            f"siteblog_article rows:  {len(existing_target_ids)} (before)"
        )

        if dry_run:
            to_copy = source_count - sum(
                1 for a in source_qs if a.pk in existing_target_ids
            )
            self.stdout.write(
                self.style.NOTICE(f"[dry-run] would copy: {to_copy} rows")
            )
            return

        with transaction.atomic():
            if truncate_target:
                deleted, _ = SiteblogArticle.objects.all().delete()
                self.stdout.write(
                    self.style.WARNING(
                        f"truncated siteblog_article ({deleted} rows)"
                    )
                )
                existing_target_ids = set()

            new_rows = []
            for src in source_qs:
                if src.pk in existing_target_ids:
                    continue
                target = SiteblogArticle(
                    pk=src.pk,
                    title=src.title,
                    article_body=src.article_body.content,
                    published_on=src.published_on,
                    slug=src.slug,
                    status=src.status,
                )
                # AutoCreated/AutoLastModified/MonitorField defaults overwrite
                # any value passed to __init__ — assign after construction so
                # bulk_create preserves the original timestamps verbatim.
                target.created = src.created
                target.modified = src.modified
                target.status_changed = src.status_changed
                new_rows.append(target)

            if not new_rows:
                self.stdout.write(self.style.SUCCESS("nothing to copy"))
                return

            SiteblogArticle.objects.bulk_create(new_rows)

            self._resync_pk_sequence()

        self.stdout.write(
            self.style.SUCCESS(f"copied {len(new_rows)} rows to siteblog_article")
        )

    @staticmethod
    def _resync_pk_sequence():
        """Bump siteblog_article's sequence past any explicit PKs we inserted.

        bulk_create with explicit ``pk`` values bypasses the sequence, so the
        next auto-generated PK would collide with an existing row.
        """
        from django.db import connection

        table = SiteblogArticle._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
            )
