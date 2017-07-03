# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('eksport_pbn', '0002_auto_20150826_0050'),
    ]

    operations = [
        migrations.AddField(
            model_name='plikeksportupbn',
            name='artykuly',
            field=models.BooleanField(default=True, verbose_name=b'Artyku\xc5\x82y'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='plikeksportupbn',
            name='ksiazki',
            field=models.BooleanField(default=True, verbose_name=b'Ksi\xc4\x85\xc5\xbcki'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='plikeksportupbn',
            name='rozdzialy',
            field=models.BooleanField(default=True, verbose_name=b'Rozdzia\xc5\x82y'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='plikeksportupbn',
            name='rok',
            field=models.IntegerField(choices=[(2013, b'2013'), (2014, b'2014'), (2015, b'2015')]),
            preserve_default=True,
        ),
    ]
