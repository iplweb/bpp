# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0010_auto_20141126_1825'),
    ]

    operations = [
        migrations.AddField(
            model_name='patent',
            name='dostep_dnia',
            field=models.DateField(null=True, verbose_name=b'Dost\xc4\x99p dnia', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='praca_doktorska',
            name='dostep_dnia',
            field=models.DateField(null=True, verbose_name=b'Dost\xc4\x99p dnia', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='praca_habilitacyjna',
            name='dostep_dnia',
            field=models.DateField(null=True, verbose_name=b'Dost\xc4\x99p dnia', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_ciagle',
            name='dostep_dnia',
            field=models.DateField(null=True, verbose_name=b'Dost\xc4\x99p dnia', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_zwarte',
            name='dostep_dnia',
            field=models.DateField(null=True, verbose_name=b'Dost\xc4\x99p dnia', blank=True),
            preserve_default=True,
        ),
    ]
