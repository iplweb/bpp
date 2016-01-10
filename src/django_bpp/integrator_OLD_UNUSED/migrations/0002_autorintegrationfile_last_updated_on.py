# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('integrator_OLD_UNUSED', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='autorintegrationfile',
            name='last_updated_on',
            field=models.DateTimeField(default=datetime.datetime(2015, 8, 24, 14, 27, 40, 542038, tzinfo=utc), auto_now=True, auto_now_add=True),
            preserve_default=False,
        ),
    ]
