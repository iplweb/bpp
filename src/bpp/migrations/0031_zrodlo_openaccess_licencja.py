# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0030_auto_20150923_1351'),
    ]

    operations = [
        migrations.AddField(
            model_name='zrodlo',
            name='openaccess_licencja',
            field=models.ForeignKey(on_delete=models.CASCADE, verbose_name=b'OpenAccess: licencja', blank=True, to='bpp.Licencja_OpenAccess', null=True),
            preserve_default=True,
        ),
    ]
