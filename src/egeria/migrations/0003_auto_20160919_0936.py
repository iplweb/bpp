# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('egeria', '0002_auto_20160919_0233'),
    ]

    operations = [
        migrations.AlterField(
            model_name='egeriarow',
            name='stanowisko',
            field=models.CharField(max_length=250),
        ),
    ]
