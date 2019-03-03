# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0069_eksport_pbn_charaktery'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patent',
            name='informacje',
            field=models.TextField(db_index=True, null=True, verbose_name=b'Informacje', blank=True),
        ),
        migrations.AlterField(
            model_name='praca_doktorska',
            name='informacje',
            field=models.TextField(db_index=True, null=True, verbose_name=b'Informacje', blank=True),
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='informacje',
            field=models.TextField(db_index=True, null=True, verbose_name=b'Informacje', blank=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='informacje',
            field=models.TextField(db_index=True, null=True, verbose_name=b'Informacje', blank=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='informacje',
            field=models.TextField(db_index=True, null=True, verbose_name=b'Informacje', blank=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='wydawnictwo_nadrzedne',
            field=models.ForeignKey(on_delete=models.CASCADE, related_name='wydawnictwa_powiazane_set', blank=True, to='bpp.Wydawnictwo_Zwarte', help_text=b'Je\xc5\xbceli dodajesz rozdzia\xc5\x82,\n        tu wybierz prac\xc4\x99, w ramach kt\xc3\xb3rej dany rozdzia\xc5\x82 wyst\xc4\x99puje.', null=True),
        ),
    ]
