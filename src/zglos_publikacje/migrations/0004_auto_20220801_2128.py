# Generated by Django 3.2.14 on 2022-08-01 19:28

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zglos_publikacje", "0003_auto_20220801_2045"),
    ]

    operations = [
        migrations.AddField(
            model_name="zgloszenie_publikacji_autor",
            name="rok",
            field=models.PositiveSmallIntegerField(default=2022),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="zgloszenie_publikacji",
            name="rok",
            field=models.IntegerField(
                db_index=True,
                help_text="Rok uwzględniany przy wyszukiwaniu i raportach\n        KBN/MNiSW)",
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
    ]