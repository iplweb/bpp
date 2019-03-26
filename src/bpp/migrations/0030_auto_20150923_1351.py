# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0029_auto_20150923_1343'),
    ]

    operations = [
        migrations.AddField(
            model_name='zrodlo',
            name='openaccess_tryb_dostepu',
            field=models.CharField(blank=True, max_length=50, verbose_name=b'OpenAccess: tryb dost\xc4\x99pu', db_index=True, choices=[(b'FULL', b'pe\xc5\x82ny'), (b'PARTIAL', b'cz\xc4\x99\xc5\x9bciowy')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='openaccess_czas_publikacji',
            field=models.ForeignKey(on_delete=models.CASCADE, verbose_name=b'OpenAccess: czas udost\xc4\x99pnienia', blank=True, to='bpp.Czas_Udostepnienia_OpenAccess', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='openaccess_licencja',
            field=models.ForeignKey(on_delete=models.CASCADE, verbose_name=b'OpenAccess: licencja', blank=True, to='bpp.Licencja_OpenAccess', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='openaccess_tryb_dostepu',
            field=models.ForeignKey(on_delete=models.CASCADE, verbose_name=b'OpenAccess: tryb dost\xc4\x99pu', blank=True, to='bpp.Tryb_OpenAccess_Wydawnictwo_Ciagle', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='openaccess_wersja_tekstu',
            field=models.ForeignKey(on_delete=models.CASCADE, verbose_name=b'OpenAccess: wersja tekstu', blank=True, to='bpp.Wersja_Tekstu_OpenAccess', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='openaccess_czas_publikacji',
            field=models.ForeignKey(on_delete=models.CASCADE, verbose_name=b'OpenAccess: czas udost\xc4\x99pnienia', blank=True, to='bpp.Czas_Udostepnienia_OpenAccess', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='openaccess_licencja',
            field=models.ForeignKey(on_delete=models.CASCADE, verbose_name=b'OpenAccess: licencja', blank=True, to='bpp.Licencja_OpenAccess', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='openaccess_wersja_tekstu',
            field=models.ForeignKey(on_delete=models.CASCADE, verbose_name=b'OpenAccess: wersja tekstu', blank=True, to='bpp.Wersja_Tekstu_OpenAccess', null=True),
            preserve_default=True,
        ),
    ]
