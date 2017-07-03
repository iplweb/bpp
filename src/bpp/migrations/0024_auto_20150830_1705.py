# -*- coding: utf-8 -*-


from django.db import models, migrations


def ustaw_charaktery(apps, schema_editor):
    Charakter_Formalny = apps.get_model('bpp', "Charakter_Formalny")

    mapping = {
        'ROZ': {'rozdzial_pbn': True},
        'ROZS': {'rozdzial_pbn': True},

        'AC': {'artykul_pbn': True},
        'FRG': {'artykul_pbn': True},
        'KOM': {'artykul_pbn': True},
        'L': {'artykul_pbn': True},
        'PRZ': {'artykul_pbn': True},
        'Supl': {'artykul_pbn': True},
        'ZRZ': {'artykul_pbn': True},

        'KS': {'ksiazka_pbn': True},
        'KSZ': {'ksiazka_pbn': True},
        'KSP': {'ksiazka_pbn': True},

    }

    for key, item in list(mapping.items()):
        try:
            obj = Charakter_Formalny.objects.get(skrot=key)
        except Charakter_Formalny.DoesNotExist:  # testy, dalej uzywamy fixtury...
            continue

        for attrname, attrvalue in list(item.items()):
            setattr(obj, attrname, attrvalue)

        obj.save()


class Migration(migrations.Migration):
    dependencies = [
        ('bpp', '0023_auto_20150830_1704'),
    ]

    operations = [
        migrations.RunPython(ustaw_charaktery)
    ]
