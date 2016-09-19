# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.db.migrations.operations.special import RunSQL


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0047_merge'),
    ]

    operations = [
        RunSQL("UPDATE bpp_jednostka SET nazwa = trim(nazwa)"),
        RunSQL("UPDATE bpp_jednostka SET nazwa = replace(nazwa, '  ', ' ')"),
        RunSQL("UPDATE bpp_jednostka SET nazwa = replace(nazwa, '  ', ' ')"),
    ]
