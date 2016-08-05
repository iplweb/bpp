# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0041_auto_20160722_2230'),
    ]

    operations = [
        migrations.AddField(
            model_name='jednostka',
            name='nie_archiwizuj',
            field=models.BooleanField(default=False, help_text=b'Je\xc5\xbceli zaznaczono to pole, to przy imporcie danych\n    na temat struktury uczelni z zewn\xc4\x99trznych \xc5\xbar\xc3\xb3de\xc5\x82 ta jednostka nie b\xc4\x99dzie przenoszona do wydzia\xc5\x82u oznaczonego\n    jako archiwalny.'),
        ),
    ]
