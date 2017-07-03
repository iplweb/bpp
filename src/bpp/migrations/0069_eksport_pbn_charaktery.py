# -*- coding: utf-8 -*-


from django.db import migrations, models

def ustaw_typy(apps, schema_editor):
    Charakter_Formalny = apps.get_model("bpp", "Charakter_Formalny")
    for skrot in ['KS', 'KSZ', 'KSP', 'PA', 'SKR']:
        chf = Charakter_Formalny.objects.get(skrot=skrot)
        chf.ksiazka_pbn = True
        chf.save()
    for skrot in ['frg', 'ROZ', 'ROZS']:
        chf = Charakter_Formalny.objects.get(skrot=skrot)
        chf.rozdzial_pbn = True
        chf.save()

def noop(apps, schema_migration):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0068_indeks_liczba_znakow'),
    ]

    operations = [
        migrations.RunPython(ustaw_typy, noop)
    ]
