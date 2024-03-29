# Generated by Django 3.2.14 on 2022-07-07 22:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pbn_api", "0034_auto_20211028_0341"),
    ]

    operations = [
        migrations.AlterField(
            model_name="conference",
            name="versions",
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name="institution",
            name="versions",
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name="journal",
            name="versions",
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name="language",
            name="language",
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name="publication",
            name="versions",
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name="publikacjainstytucji",
            name="snapshot",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="publisher",
            name="versions",
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name="scientist",
            name="from_institution_api",
            field=models.BooleanField(
                db_index=True, null=True, verbose_name="Rekord z API instytucji"
            ),
        ),
        migrations.AlterField(
            model_name="scientist",
            name="versions",
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name="sentdata",
            name="data_sent",
            field=models.JSONField(verbose_name="Wysłane dane"),
        ),
    ]
