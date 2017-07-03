# -*- coding: utf-8 -*-


from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0002_auto_20141020_1738'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patent',
            name='utworzono',
            field=models.DateTimeField(default=datetime.datetime(1970, 1, 1, 0, 0), auto_now_add=True, verbose_name=b'Utworzono', db_index=True),
        ),
        migrations.AlterField(
            model_name='praca_doktorska',
            name='utworzono',
            field=models.DateTimeField(default=datetime.datetime(1970, 1, 1, 0, 0), auto_now_add=True, verbose_name=b'Utworzono', db_index=True),
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='utworzono',
            field=models.DateTimeField(default=datetime.datetime(1970, 1, 1, 0, 0), auto_now_add=True, verbose_name=b'Utworzono', db_index=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='utworzono',
            field=models.DateTimeField(default=datetime.datetime(1970, 1, 1, 0, 0), auto_now_add=True, verbose_name=b'Utworzono', db_index=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='utworzono',
            field=models.DateTimeField(default=datetime.datetime(1970, 1, 1, 0, 0), auto_now_add=True, verbose_name=b'Utworzono', db_index=True),
        ),
    ]
