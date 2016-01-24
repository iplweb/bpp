# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import djorm_pgfulltext.fields


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0036_auto_20160117_2147'),
    ]

    operations = [
        migrations.AlterField(
            model_name='autor',
            name='search',
            field=djorm_pgfulltext.fields.VectorField(),
        ),
        migrations.AlterField(
            model_name='jednostka',
            name='search',
            field=djorm_pgfulltext.fields.VectorField(),
        ),
        migrations.AlterField(
            model_name='patent',
            name='search_index',
            field=djorm_pgfulltext.fields.VectorField(),
        ),
        migrations.AlterField(
            model_name='praca_doktorska',
            name='search_index',
            field=djorm_pgfulltext.fields.VectorField(),
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='search_index',
            field=djorm_pgfulltext.fields.VectorField(),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='search_index',
            field=djorm_pgfulltext.fields.VectorField(),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='search_index',
            field=djorm_pgfulltext.fields.VectorField(),
        ),
        migrations.AlterField(
            model_name='zrodlo',
            name='search',
            field=djorm_pgfulltext.fields.VectorField(),
        ),
    ]
