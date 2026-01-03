from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pbn_export_queue", "0003_add_rodzaj_bledu"),
    ]

    operations = [
        migrations.AddField(
            model_name="pbn_export_queue",
            name="wykluczone",
            field=models.BooleanField(
                default=False,
                db_index=True,
                verbose_name="Wykluczone z eksportu",
                help_text="Publikacja wykluczona z eksportu z przyczyn projektowych (nie błąd)",
            ),
        ),
    ]
