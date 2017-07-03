# -*- coding: utf-8 -*-


from django.db import models, migrations
import bpp.fields


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0032_auto_20151001_1413'),
    ]

    operations = [
        migrations.AddField(
            model_name='praca_doktorska',
            name='doi',
            field=bpp.fields.DOIField(max_length=2048, blank=True, help_text=b'Digital Object Identifier (DOI)', null=True, verbose_name=b'DOI', db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='praca_habilitacyjna',
            name='doi',
            field=bpp.fields.DOIField(max_length=2048, blank=True, help_text=b'Digital Object Identifier (DOI)', null=True, verbose_name=b'DOI', db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_ciagle',
            name='doi',
            field=bpp.fields.DOIField(max_length=2048, blank=True, help_text=b'Digital Object Identifier (DOI)', null=True, verbose_name=b'DOI', db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_zwarte',
            name='doi',
            field=bpp.fields.DOIField(max_length=2048, blank=True, help_text=b'Digital Object Identifier (DOI)', null=True, verbose_name=b'DOI', db_index=True),
            preserve_default=True,
        ),
    ]
