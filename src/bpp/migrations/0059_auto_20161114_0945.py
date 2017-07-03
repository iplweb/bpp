# -*- coding: utf-8 -*-


from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0058_auto_20161113_2332'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='wydzial',
            name='archiwalny',
        ),
        migrations.RemoveField(
            model_name='wydzial',
            name='wirtualny',
        ),
        migrations.AddField(
            model_name='wydzial',
            name='otwarcie',
            field=models.DateField(default=datetime.date(2016, 11, 14), verbose_name=b'Data otwarcia wydzia\xc5\x82u', auto_now_add=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='wydzial',
            name='zamkniecie',
            field=models.DateField(null=True, verbose_name=b'Data zamkni\xc4\x99cia wydzia\xc5\x82u', blank=True),
        ),
        migrations.AddField(
            model_name='wydzial',
            name='zarzadzaj_automatycznie',
            field=models.BooleanField(default=True, help_text=b"Wydzia\xc5\x82 ten b\xc4\x99dzie dowolnie modyfikowany przez procedury importujace dane z zewn\xc4\x99trznych\n        system\xc3\xb3w informatycznych. W przypadku, gdy pole ma ustawion\xc4\x85 warto\xc5\x9b\xc4\x87 na 'fa\xc5\x82sz', wydzia\xc5\x82 ten mo\xc5\xbce by\xc4\x87", verbose_name=b'Zarz\xc4\x85dzaj automatycznie'),
        ),
    ]
