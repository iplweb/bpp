# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eksport_pbn', '0006_auto_20151203_1418'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='plikeksportupbn',
            name='rok',
        ),
        migrations.AddField(
            model_name='plikeksportupbn',
            name='do_roku',
            field=models.IntegerField(default=2016, choices=[(2013, b'2013'), (2014, b'2014'), (2015, b'2015'), (2016, b'2016')]),
        ),
        migrations.AddField(
            model_name='plikeksportupbn',
            name='od_roku',
            field=models.IntegerField(default=2016, choices=[(2013, b'2013'), (2014, b'2014'), (2015, b'2015'), (2016, b'2016')]),
        ),
        migrations.AlterField(
            model_name='plikeksportupbn',
            name='do_daty',
            field=models.DateField(null=True, verbose_name=b'Do daty', blank=True),
        ),
    ]
