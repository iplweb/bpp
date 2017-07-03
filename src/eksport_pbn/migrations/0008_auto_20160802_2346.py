# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eksport_pbn', '0007_auto_20160127_0836'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plikeksportupbn',
            name='rodzaj_daty',
            field=models.SmallIntegerField(default=3, help_text=b'Jakie pole z dat\xc4\x85 b\xc4\x99dzie u\xc5\xbcywane do wybierania rekord\xc3\xb3w?', verbose_name=b'Rodzaj pola daty', choices=[(1, b'data utworzenia'), (2, b'data aktualizacji'), (3, b'data aktualizacji dla PBN')]),
        ),
    ]
