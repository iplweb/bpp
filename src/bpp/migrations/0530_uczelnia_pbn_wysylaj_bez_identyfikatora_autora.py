from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0529_motyw_zapisany"),
    ]

    operations = [
        migrations.AddField(
            model_name="uczelnia",
            name="pbn_wysylaj_bez_identyfikatora_autora",
            field=models.BooleanField(
                default=False,
                help_text="Domyślnie wyłączone: praca, w której autor z przypiętą "
                "dyscypliną nie ma ani odpowiednika w PBN, ani ORCID, nie jest "
                "wysyłana do PBN, dopóki ktoś nie uzupełni danych autora. Po "
                "włączeniu taka praca jest wysyłana, ale BEZ oświadczenia tego "
                "autora — przy wysyłce pojawia się ostrzeżenie z liczbą oświadczeń, "
                "które trafią do PBN, i listą pominiętych autorów.",
                verbose_name="Wysyłaj prace, gdy autor nie ma identyfikatora w PBN",
            ),
        ),
    ]
