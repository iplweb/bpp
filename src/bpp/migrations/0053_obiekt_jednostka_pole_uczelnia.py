# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0052_skupia_pracownikow_zarzadzaj_automatycznie'),
    ]

    operations = [
        migrations.AddField(
            model_name='jednostka',
            name='uczelnia',
            field=models.ForeignKey(on_delete=models.CASCADE, default=1, to='bpp.Uczelnia'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='uczelnia',
            name='obca_jednostka',
            field=models.ForeignKey(on_delete=models.CASCADE, related_name='obca_jednostka', blank=True, to='bpp.Jednostka', help_text=b'\n    Jednostka skupiaj\xc4\x85ca autor\xc3\xb3w nieindeksowanych, nie b\xc4\x99d\xc4\x85cych pracownikami uczelni. Procedury importuj\xc4\x85ce\n    dane z zewn\xc4\x99trznych system\xc3\xb3w informatycznych b\xc4\x99d\xc4\x85 przypisywa\xc4\x87 do tej jednostki osoby, kt\xc3\xb3re zako\xc5\x84czy\xc5\x82y\n    prac\xc4\x99 na uczelni. ', null=True),
        ),
    ]
