# -*- coding: utf-8 -*-


from django.db import migrations, models
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0072_gist_to_gin'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patent',
            name='opis_bibliograficzny_autorzy_cache',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.TextField(), blank=True),
        ),
        migrations.AlterField(
            model_name='praca_doktorska',
            name='opis_bibliograficzny_autorzy_cache',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.TextField(), blank=True),
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='opis_bibliograficzny_autorzy_cache',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.TextField(), blank=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='opis_bibliograficzny_autorzy_cache',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.TextField(), blank=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='opis_bibliograficzny_autorzy_cache',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.TextField(), blank=True),
        ),
    ]
