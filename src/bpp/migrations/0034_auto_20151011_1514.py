# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0033_auto_20151001_1425'),
    ]

    operations = [
        migrations.AddField(
            model_name='wydawnictwo_ciagle',
            name='openaccess_ilosc_miesiecy',
            field=models.PositiveIntegerField(help_text=b'Ilo\xc5\x9b\xc4\x87 miesi\xc4\x99cy jakie up\xc5\x82yn\xc4\x99\xc5\x82y od momentu opublikowania do momentu udost\xc4\x99pnienia', null=True, verbose_name=b'OpenAccess: ilo\xc5\x9b\xc4\x87 miesi\xc4\x99cy', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_zwarte',
            name='openaccess_ilosc_miesiecy',
            field=models.PositiveIntegerField(help_text=b'Ilo\xc5\x9b\xc4\x87 miesi\xc4\x99cy jakie up\xc5\x82yn\xc4\x99\xc5\x82y od momentu opublikowania do momentu udost\xc4\x99pnienia', null=True, verbose_name=b'OpenAccess: ilo\xc5\x9b\xc4\x87 miesi\xc4\x99cy', blank=True),
            preserve_default=True,
        ),
    ]
