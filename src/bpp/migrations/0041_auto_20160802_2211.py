# -*- coding: utf-8 -*-


from django.db import migrations, models
from datetime import datetime

class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0040_auto_20160802_2209'),
    ]

    operations = [
        migrations.AddField(
            model_name='wydawnictwo_ciagle',
            name='ostatnio_zmieniony_dla_pbn',
            field=models.DateTimeField(default='2001-01-01 00:00', auto_now_add=True, help_text=b'Ostatnia aktualizacja rekordu - zmiana dowolnego z p\xc3\xb3l z awyj\xc4\x85tkiem blok\xc3\xb3w p\xc3\xb3l: \xe2\x80\x9epunktacja\xe2\x80\x9d,\n        \xe2\x80\x9epunktacja komisji centralnej\xe2\x80\x9d, \xe2\x80\x9eadnotacje\xe2\x80\x9d oraz pole \xe2\x80\x9estatus korekty\xe2\x80\x9d.', verbose_name=b'Ostatnio zmieniony (dla PBN)'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='wydawnictwo_zwarte',
            name='ostatnio_zmieniony_dla_pbn',
            field=models.DateTimeField(default='2001-01-01 00:00', auto_now_add=True, help_text=b'Ostatnia aktualizacja rekordu - zmiana dowolnego z p\xc3\xb3l z awyj\xc4\x85tkiem blok\xc3\xb3w p\xc3\xb3l: \xe2\x80\x9epunktacja\xe2\x80\x9d,\n        \xe2\x80\x9epunktacja komisji centralnej\xe2\x80\x9d, \xe2\x80\x9eadnotacje\xe2\x80\x9d oraz pole \xe2\x80\x9estatus korekty\xe2\x80\x9d.', verbose_name=b'Ostatnio zmieniony (dla PBN)'),
            preserve_default=False,
        ),
        migrations.RunSQL("UPDATE bpp_wydawnictwo_ciagle SET ostatnio_zmieniony_dla_pbn = ostatnio_zmieniony"),
        migrations.RunSQL("UPDATE bpp_wydawnictwo_zwarte SET ostatnio_zmieniony_dla_pbn = ostatnio_zmieniony"),
    ]
