from django.db import migrations

MAPA = {"normalna": "Standard", "kolo_naukowe": "Koło naukowe"}


def backfill(apps, schema_editor):
    Jednostka = apps.get_model("bpp", "Jednostka")
    RodzajJednostki = apps.get_model("bpp", "RodzajJednostki")
    cache = {n: RodzajJednostki.objects.get(nazwa=n) for n in MAPA.values()}
    for kod, nazwa in MAPA.items():
        Jednostka.objects.filter(rodzaj_jednostki=kod, rodzaj__isnull=True).update(
            rodzaj=cache[nazwa]
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0449_jednostka_rodzaj"),
        ("bpp", "0448_seed_rodzajjednostki"),
    ]
    operations = [migrations.RunPython(backfill, noop)]
