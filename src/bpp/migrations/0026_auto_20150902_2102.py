# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0025_auto_20150830_1740'),
    ]

    operations = [
        migrations.AlterField(
            model_name='praca_doktorska',
            name='autor',
            field=models.ForeignKey(on_delete=models.CASCADE, to='bpp.Autor', unique=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='autor',
            field=models.ForeignKey(on_delete=models.CASCADE, to='bpp.Autor', unique=True),
            preserve_default=True,
        ),
    ]
