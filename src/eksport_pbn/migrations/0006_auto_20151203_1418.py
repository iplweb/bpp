# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('eksport_pbn', '0005_auto_20151202_2204'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='plikeksportupbn',
            name='data',
        ),
        migrations.AddField(
            model_name='plikeksportupbn',
            name='do_daty',
            field=models.DateField(null=True, verbose_name=b'Od daty', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='plikeksportupbn',
            name='od_daty',
            field=models.DateField(null=True, verbose_name=b'Od daty', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='plikeksportupbn',
            name='rodzaj_daty',
            field=models.SmallIntegerField(default=0, help_text=b'Jakie pole z dat\xc4\x85 b\xc4\x99dzie u\xc5\xbcywane do wybierania rekord\xc3\xb3w?', verbose_name=b'Rodzaj pola daty', choices=[(1, b'data utworzenia'), (2, b'data aktualizacji')]),
            preserve_default=True,
        ),
    ]
