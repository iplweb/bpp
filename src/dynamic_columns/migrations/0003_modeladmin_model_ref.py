# Generated by Django 3.2.15 on 2022-10-02 21:38

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("dynamic_columns", "0002_auto_20221002_2252"),
    ]

    operations = [
        migrations.AddField(
            model_name="modeladmin",
            name="model_ref",
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.CASCADE,
                to="contenttypes.contenttype",
            ),
            preserve_default=False,
        ),
    ]