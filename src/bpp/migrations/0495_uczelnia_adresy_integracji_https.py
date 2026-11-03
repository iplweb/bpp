from django.db import migrations

POLA = ("pbn_api_root", "dspace_api_endpoint")
STARY = "http://"
NOWY = "https://"


def http_na_https(apps, schema_editor):
    """Adresy integracji uczelni muszą zaczynać się od https:// — zamień
    prefiks w istniejących rekordach, żeby zapis Uczelni nie był blokowany
    przez walidację."""
    Uczelnia = apps.get_model("bpp", "Uczelnia")
    for uczelnia in Uczelnia.objects.all().only("pk", *POLA):
        zmiany = {}
        for pole in POLA:
            wartosc = getattr(uczelnia, pole) or ""
            if wartosc[: len(STARY)].lower() == STARY:
                zmiany[pole] = NOWY + wartosc[len(STARY) :]
        if zmiany:
            Uczelnia.objects.filter(pk=uczelnia.pk).update(**zmiany)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0494_autor_opis_do_adnotacji"),
    ]

    operations = [
        migrations.RunPython(http_na_https, migrations.RunPython.noop),
    ]
