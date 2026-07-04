from django.db import migrations

SEED = [
    # nazwa, wyklucz_z_rankingu_autorow, pokazuj_jako_odrebna_sekcje, kolejnosc
    ("Standard", False, False, 0),
    ("Koło naukowe", True, True, 1),
    ("Wydział", False, False, 2),
]


def seed(apps, schema_editor):
    RodzajJednostki = apps.get_model("bpp", "RodzajJednostki")
    for nazwa, wyklucz, sekcja, kolejnosc in SEED:
        RodzajJednostki.objects.update_or_create(
            nazwa=nazwa,
            defaults={
                "wyklucz_z_rankingu_autorow": wyklucz,
                "pokazuj_jako_odrebna_sekcje": sekcja,
                "kolejnosc": kolejnosc,
            },
        )


def unseed(apps, schema_editor):
    RodzajJednostki = apps.get_model("bpp", "RodzajJednostki")
    RodzajJednostki.objects.filter(nazwa__in=[n for n, *_ in SEED]).delete()


class Migration(migrations.Migration):
    dependencies = [("bpp", "0445_rodzajjednostki")]
    operations = [migrations.RunPython(seed, unseed)]
