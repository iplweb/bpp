# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0011_auto_20150212_2203'),
    ]

    operations = [
        migrations.AddField(
            model_name='wydzial',
            name='poprzednie_nazwy',
            field=models.CharField(default=b'', max_length=4096, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='patent',
            name='dostep_dnia',
            field=models.DateField(help_text=b'Data dost\xc4\x99pu do strony WWW.', null=True, verbose_name=b'Dost\xc4\x99p dnia', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='praca_doktorska',
            name='dostep_dnia',
            field=models.DateField(help_text=b'Data dost\xc4\x99pu do strony WWW.', null=True, verbose_name=b'Dost\xc4\x99p dnia', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='dostep_dnia',
            field=models.DateField(help_text=b'Data dost\xc4\x99pu do strony WWW.', null=True, verbose_name=b'Dost\xc4\x99p dnia', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='dostep_dnia',
            field=models.DateField(help_text=b'Data dost\xc4\x99pu do strony WWW.', null=True, verbose_name=b'Dost\xc4\x99p dnia', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='dostep_dnia',
            field=models.DateField(help_text=b'Data dost\xc4\x99pu do strony WWW.', null=True, verbose_name=b'Dost\xc4\x99p dnia', blank=True),
            preserve_default=True,
        ),
    ]
