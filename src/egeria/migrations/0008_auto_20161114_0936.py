# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('egeria', '0007_auto_20161113_2332'),
    ]

    operations = [
        migrations.AlterField(
            model_name='egeriaimport',
            name='od',
            field=models.DateField(auto_now_add=True),
        ),
    ]
