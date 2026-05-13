"""Initial schema for django-site-blog, regenerated for model-utils 5.x.

Mirrors siteblog 0.1.0's models exactly but builds the migration without the
4.x-only ``SplitField(no_excerpt_field=True)`` kwarg. ``_article_body_excerpt``
is declared explicitly here (model-utils 5's ``SplitField.contribute_to_class``
adds it at runtime, but the migration still needs to materialize the column).
"""
import django.contrib.sites.managers
import django.db.models.manager
import django.utils.timezone
import model_utils.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.CreateModel(
            name="Article",
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
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "status",
                    model_utils.fields.StatusField(
                        choices=[("draft", "draft"), ("published", "published")],
                        default="draft",
                        max_length=100,
                        no_check_for_status=True,
                        verbose_name="status",
                    ),
                ),
                (
                    "status_changed",
                    model_utils.fields.MonitorField(
                        default=django.utils.timezone.now,
                        monitor="status",
                        verbose_name="status changed",
                    ),
                ),
                ("title", models.TextField(verbose_name="Title")),
                (
                    "article_body",
                    model_utils.fields.SplitField(
                        help_text=(
                            "Użyj znacznika podziału „&lt;!-- tutaj --&gt;” "
                            "w przypadku jeżeli chcesz wyświetlić krótszą "
                            "wersję treści artykułu"
                        ),
                        verbose_name="Article body",
                    ),
                ),
                (
                    "_article_body_excerpt",
                    models.TextField(editable=False),
                ),
                (
                    "published_on",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        verbose_name="Published on",
                    ),
                ),
                ("slug", models.SlugField(unique=True)),
                (
                    "sites",
                    models.ManyToManyField(
                        blank=True,
                        help_text=(
                            "Restrict this article to selected sites. "
                            "Leave empty to make it visible on all sites."
                        ),
                        related_name="articles",
                        to="sites.site",
                        verbose_name="Sites",
                    ),
                ),
            ],
            options={
                "verbose_name": "Article",
                "verbose_name_plural": "Articles",
                "ordering": ("-published_on", "title"),
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                (
                    "on_site",
                    django.contrib.sites.managers.CurrentSiteManager("sites"),
                ),
            ],
        ),
    ]
