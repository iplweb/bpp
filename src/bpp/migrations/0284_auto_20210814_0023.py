# Generated by Django 3.0.14 on 2021-08-13 22:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0283_auto_20210809_0142"),
    ]

    operations = [
        migrations.CreateModel(
            name="BppMultiseekVisibility",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(db_index=True, max_length=50, unique=True)),
                ("label", models.CharField(max_length=200)),
                (
                    "public",
                    models.BooleanField(
                        default=True, verbose_name="Widoczne dla wszystkich"
                    ),
                ),
                (
                    "authenticated",
                    models.BooleanField(
                        default=True, verbose_name="Widoczne dla zalogowanych"
                    ),
                ),
                (
                    "staff",
                    models.BooleanField(
                        default=True, verbose_name='Widoczne dla osób "w zespole"'
                    ),
                ),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
            ],
        ),
    ]