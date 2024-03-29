# Generated by Django 3.2.15 on 2022-09-10 19:14

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("zglos_publikacje", "0012_auto_20220910_1654"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name="obslugujacy_zgloszenia_wydzialow",
            managers=[],
        ),
        migrations.AddField(
            model_name="zgloszenie_publikacji",
            name="utworzyl",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
                verbose_name="Utworzył",
            ),
        ),
    ]
