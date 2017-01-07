# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('egeria', '0006_auto_20161030_0935'),
    ]

    operations = [
        migrations.AddField(
            model_name='egeriaimport',
            name='do',
            field=models.DateField(help_text=b'\n    Uwaga, to pole jest opcjonalne, a w przypadku importu danych aktualnych (tzn. obowi\xc4\x85zuj\xc4\x85cych\n    OD danego terminu, ale nie maj\xc4\x85cych wyra\xc5\xbanego "zako\xc5\x84czenia" w przysz\xc5\x82o\xc5\x9bci) - powinno\n    pozosta\xc4\x87 puste!', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='egeriaimport',
            name='od',
            field=models.DateField(default=datetime.date(2016, 11, 13)),
            preserve_default=False,
        ),
    ]
