import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    # 0019 jest jedynym liściem grafu tej aplikacji (historia ma zdublowane
    # numery 0005/0006/0007/0012 pościnane merge'ami 0006/0007/0011/0013,
    # ale od 0014 gałąź jest już liniowa). Numer 0020 podany jawnie, żeby
    # równoległa gałąź nie dorobiła kolejnego duba.
    dependencies = [
        ("importer_publikacji", "0019_multipleworksimport_uczelnia"),
        # FK celuje w Zgloszenie_Publikacji; migracja 0027 dokłada tam status
        # ZAIMPORTOWANY + pola audytowe (druga połowa tej samej zmiany).
        ("zglos_publikacje", "0027_zgloszenie_zaimportowane"),
    ]

    operations = [
        migrations.AddField(
            model_name="importsession",
            name="zgloszenie",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Zgłoszenie publikacji, które ten import domyka. "
                    "Ustawiane jawnie (przycisk „Użyj importera”) albo "
                    "automatycznie po DOI. Zadanie Celery dostaje wyłącznie "
                    "id sesji — bez tego pola nie miałoby jak ustalić, "
                    "które zgłoszenie oznaczyć."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sesje_importu",
                to="zglos_publikacje.zgloszenie_publikacji",
                verbose_name="Zgłoszenie publikacji",
            ),
        ),
        migrations.AddField(
            model_name="importsession",
            name="zgloszenie_odrzucone_przez_operatora",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Operator kliknął „żadne z nich” na banerze kandydatów "
                    "— baner nie pokazuje się już dla tej sesji."
                ),
                verbose_name="Operator odrzucił propozycje zgłoszeń",
            ),
        ),
    ]
