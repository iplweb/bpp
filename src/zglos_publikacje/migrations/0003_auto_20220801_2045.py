# Generated by Django 3.2.14 on 2022-08-01 18:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zglos_publikacje", "0002_auto_20220710_2331"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="zgloszenie_publikacji",
            options={
                "ordering": ("-utworzono", "tytul_oryginalny"),
                "verbose_name": "zgłoszenie publikacji",
                "verbose_name_plural": "zgłoszenia publikacji",
            },
        ),
        migrations.AddField(
            model_name="zgloszenie_publikacji",
            name="rok",
            field=models.IntegerField(
                db_index=True,
                default=2022,
                help_text="Rok uwzględniany przy wyszukiwaniu i raportach\n        KBN/MNiSW)",
            ),
            preserve_default=False,
        ),
    ]