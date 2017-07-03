# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('eksport_pbn', '0003_auto_20150830_1633'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plikeksportupbn',
            name='rok',
            field=models.IntegerField(default=2015, choices=[(2013, b'2013'), (2014, b'2014'), (2015, b'2015')]),
            preserve_default=True,
        ),
    ]
