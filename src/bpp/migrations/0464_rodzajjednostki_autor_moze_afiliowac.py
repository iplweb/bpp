from django.db import migrations, models


def wydzial_bez_afiliacji(apps, schema_editor):
    """#438: rodzaj „Wydział" domyślnie nie przyjmuje afiliacji autorów —
    afiliacja powinna wskazywać jednostkę podrzędną, nie korzeń-wydział."""
    RodzajJednostki = apps.get_model("bpp", "RodzajJednostki")
    RodzajJednostki.objects.filter(nazwa="Wydział").update(autor_moze_afiliowac=False)


def wydzial_bez_afiliacji_rev(apps, schema_editor):
    RodzajJednostki = apps.get_model("bpp", "RodzajJednostki")
    RodzajJednostki.objects.filter(nazwa="Wydział").update(autor_moze_afiliowac=True)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0463_faza_b_iv2_multiseek_values"),
    ]

    operations = [
        migrations.AddField(
            model_name="rodzajjednostki",
            name="autor_moze_afiliowac",
            field=models.BooleanField(
                default=True,
                help_text="Gdy odznaczone, autorów prac nie można afiliować na "
                "jednostki tego rodzaju — np. wydziały: afiliacja powinna "
                "wskazywać jednostkę podrzędną, nie sam wydział.",
                verbose_name="Autor może afiliować",
            ),
        ),
        migrations.RunPython(wydzial_bez_afiliacji, wydzial_bez_afiliacji_rev),
    ]
