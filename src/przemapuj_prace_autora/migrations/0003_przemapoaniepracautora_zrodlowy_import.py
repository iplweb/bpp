import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "przemapuj_prace_autora",
            "0002_przemapoaniepracautora_prace_ciagle_historia_and_more",
        ),
        ("import_pracownikow", "0015_przepnij_prace"),
    ]

    operations = [
        migrations.AddField(
            model_name="przemapoaniepracautora",
            name="zrodlowy_import",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="przemapowania",
                to="import_pracownikow.importpracownikow",
                verbose_name="Import pracowników",
            ),
        ),
    ]
