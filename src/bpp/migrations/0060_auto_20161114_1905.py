# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0059_auto_20161114_0945'),
    ]

    operations = [
        migrations.AlterField(
            model_name='wydzial',
            name='otwarcie',
            field=models.DateField(null=True, verbose_name=b'Data otwarcia wydzia\xc5\x82u', blank=True),
        ),
    ]
