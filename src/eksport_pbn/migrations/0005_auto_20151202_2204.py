# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('eksport_pbn', '0004_auto_20150830_1740'),
    ]

    operations = [
        migrations.AddField(
            model_name='plikeksportupbn',
            name='data',
            field=models.DateField(help_text=b'Data aktualizacji lub utworzenia rekordu wi\xc4\x99ksza od lub r\xc3\xb3wna...', null=True, verbose_name=b'Data', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='plikeksportupbn',
            name='rodzaj_daty',
            field=models.SmallIntegerField(default=0, verbose_name=b'Rodzaj pola daty', choices=[(1, b'data utworzenia'), (2, b'data aktualizacji')]),
            preserve_default=True,
        ),
    ]
