# Generated by Django 3.2.14 on 2022-07-07 22:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0002_notification_acknowledged"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="notification",
            options={"ordering": ("created_on",)},
        ),
        migrations.AlterField(
            model_name="notification",
            name="acknowledged",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AlterField(
            model_name="notification",
            name="values",
            field=models.JSONField(),
        ),
    ]