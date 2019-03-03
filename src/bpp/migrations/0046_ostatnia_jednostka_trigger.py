# -*- coding: utf-8 -*-


from django.db import migrations
from django.db.migrations.operations.special import RunPython
from django.db import migrations, models

from bpp.migration_util import load_custom_sql


class Migration(migrations.Migration):
    dependencies = [
        ('bpp', '0045_auto_20160809_0004'),
    ]

    operations = [
        migrations.AddField(
            model_name='autor',
            name='aktualna_funkcja',
            field=models.ForeignKey(on_delete=models.CASCADE, related_name='aktualna_funkcja', blank=True, to='bpp.Funkcja_Autora', null=True),
        ),
        RunPython(
            lambda *args, **kw: load_custom_sql("0046_ostatnia_jednostka_trigger"),
            lambda *args, **kw: load_custom_sql("0046_ostatnia_jednostka_trigger_remove.sql"))
    ]
