# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def ustaw_typy_kbn(apps, schema_editor):
    Typ_KBN = apps.get_model("bpp", "Typ_KBN")
    for elem in Typ_KBN.objects.all():
        elem.artykul_pbn = True
        if elem.skrot in ['000', 'PW']:
            elem.artykul_pbn = False
        elem.save()

    Charakter_Formalny = apps.get_model("bpp", "Charakter_Formalny")
    for elem in ["SKR", "PA"]:
        s = Charakter_Formalny.objects.get(skrot=elem)
        s.ksiazka_pbn = True
        s.save()

    for elem in ["ROZS", "frg"]:
        s = Charakter_Formalny.objects.get(skrot=elem)
        s.rozdzial_pbn = True
        s.save()

def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('bpp', '0066_wydawnictwo_zwarte_calkowita_liczba_autorow'),
    ]

    operations = [
        migrations.AddField(
            model_name='typ_kbn',
            name='artykul_pbn',
            field=models.BooleanField(default=False,
                                      help_text=b'Wydawnictwa ci\xc4\x85g\xc5\x82e posiadaj\xc4\x85ce\n    ten typ KBN zostan\xc4\x85 w\xc5\x82\xc4\x85czone do eksportu PBN jako artyku\xc5\x82y',
                                      verbose_name=b'Artyku\xc5\x82 w PBN'),
        ),
        migrations.RunPython(ustaw_typy_kbn, noop)
    ]
