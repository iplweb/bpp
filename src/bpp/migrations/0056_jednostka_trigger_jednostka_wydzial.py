# -*- coding: utf-8 -*-


from django.db import migrations, models

from bpp.migration_util import load_custom_sql


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0055_jednostka_wydzial'),
    ]

    operations = [
        migrations.RunPython(lambda *args, **kw: load_custom_sql("0056_jednostka_trigger_jednostka_wydzial")),

    ]
