from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0490_usun_unique_autor_kolejnosc"),
    ]

    operations = [
        migrations.AddField(
            model_name="uczelnia",
            name="kreator_czeka_na_pbn",
            field=models.BooleanField(
                default=False,
                editable=False,
                help_text="Ustawiane przez kreator po utworzeniu uczelni, "
                "kasowane po odpowiedzi na pytanie o integrację z PBN (zapis "
                "albo pominięcie). Uczelnie spoza kreatora mają tu zawsze False.",
                verbose_name="Kreator pierwszego uruchomienia czeka na odpowiedź o PBN",
            ),
        ),
    ]
