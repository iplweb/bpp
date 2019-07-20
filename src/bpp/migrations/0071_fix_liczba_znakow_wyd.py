# -*- coding: utf-8 -*-


from django.db import migrations, models

from bpp.migration_util import load_custom_sql


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0070_auto_20170220_1757'),
    ]

    operations = [
        migrations.RunPython(lambda *args, **kw: load_custom_sql("0071_fix_liczba_znakow_wyd")),
    ]
