# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0028_openaccess'),
    ]

    operations = [
        migrations.AddField(
            model_name='wydawnictwo_ciagle',
            name='openaccess_czas_publikacji',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='bpp.Czas_Udostepnienia_OpenAccess', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_ciagle',
            name='openaccess_licencja',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='bpp.Licencja_OpenAccess', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_ciagle',
            name='openaccess_tryb_dostepu',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='bpp.Tryb_OpenAccess_Wydawnictwo_Ciagle', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_ciagle',
            name='openaccess_wersja_tekstu',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='bpp.Wersja_Tekstu_OpenAccess', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_zwarte',
            name='openaccess_czas_publikacji',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='bpp.Czas_Udostepnienia_OpenAccess', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_zwarte',
            name='openaccess_licencja',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='bpp.Licencja_OpenAccess', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_zwarte',
            name='openaccess_tryb_dostepu',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='bpp.Tryb_OpenAccess_Wydawnictwo_Zwarte', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_zwarte',
            name='openaccess_wersja_tekstu',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='bpp.Wersja_Tekstu_OpenAccess', null=True),
            preserve_default=True,
        ),
    ]
