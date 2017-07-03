# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0059_auto_20161114_0945'),
        ('egeria', '0008_auto_20161114_0936'),
    ]

    operations = [
        migrations.AddField(
            model_name='egeriaimport',
            name='uczelnia',
            field=models.ForeignKey(default=1, to='bpp.Uczelnia'),
            preserve_default=False,
        ),
    ]
