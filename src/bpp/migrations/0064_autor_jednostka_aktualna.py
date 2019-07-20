# -*- coding: utf-8 -*-


from django.db import migrations, models

from bpp.migration_util import load_custom_sql

class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0063_autor_aktualny'),
    ]

    operations = [
        migrations.RunPython(lambda *args, **kw: load_custom_sql("0064_autor_jednostka_aktualna")),

    ]
