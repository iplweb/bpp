# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('bpp', '0041_auto_20160802_2211'),
    ]

    operations = [
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='ostatnio_zmieniony_dla_pbn',
            field=models.DateTimeField(
                help_text=b'Moment ostatniej aktualizacji rekordu dla potrzeb PBN. To pole zmieni si\xc4\x99 automatycznie, gdy\n        nast\xc4\x85pi zmiana dowolnego z p\xc3\xb3l za wyj\xc4\x85tkiem blok\xc3\xb3w p\xc3\xb3l: \xe2\x80\x9epunktacja\xe2\x80\x9d, \xe2\x80\x9epunktacja komisji centralnej\xe2\x80\x9d,\n        \xe2\x80\x9eadnotacje\xe2\x80\x9d oraz pole \xe2\x80\x9estatus korekty\xe2\x80\x9d.',
                verbose_name=b'Ostatnio zmieniony (dla PBN)', auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='ostatnio_zmieniony_dla_pbn',
            field=models.DateTimeField(
                help_text=b'Moment ostatniej aktualizacji rekordu dla potrzeb PBN. To pole zmieni si\xc4\x99 automatycznie, gdy\n        nast\xc4\x85pi zmiana dowolnego z p\xc3\xb3l za wyj\xc4\x85tkiem blok\xc3\xb3w p\xc3\xb3l: \xe2\x80\x9epunktacja\xe2\x80\x9d, \xe2\x80\x9epunktacja komisji centralnej\xe2\x80\x9d,\n        \xe2\x80\x9eadnotacje\xe2\x80\x9d oraz pole \xe2\x80\x9estatus korekty\xe2\x80\x9d.',
                verbose_name=b'Ostatnio zmieniony (dla PBN)', auto_now_add=True),
        ),

    ]
