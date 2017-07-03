# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0012_auto_20150530_1733'),
    ]

    operations = [
        migrations.AddField(
            model_name='wydzial',
            name='zezwalaj_na_ranking_autorow',
            field=models.BooleanField(default=True, verbose_name=b'Zezwalaj na generowanie rankingu autor\xc3\xb3w dla tego wydzia\xc5\x82u'),
            preserve_default=True,
        ),
    ]
