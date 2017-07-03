# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0026_auto_20150902_2102'),
    ]

    operations = [
        migrations.AlterField(
            model_name='praca_doktorska',
            name='e_isbn',
            field=models.CharField(db_index=True, max_length=64, null=True, verbose_name=b'E-ISBN', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='praca_doktorska',
            name='isbn',
            field=models.CharField(db_index=True, max_length=64, null=True, verbose_name=b'ISBN', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='e_isbn',
            field=models.CharField(db_index=True, max_length=64, null=True, verbose_name=b'E-ISBN', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='isbn',
            field=models.CharField(db_index=True, max_length=64, null=True, verbose_name=b'ISBN', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='e_isbn',
            field=models.CharField(db_index=True, max_length=64, null=True, verbose_name=b'E-ISBN', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='isbn',
            field=models.CharField(db_index=True, max_length=64, null=True, verbose_name=b'ISBN', blank=True),
            preserve_default=True,
        ),
    ]
