# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-06-21 22:57


from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0074_django110'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patent',
            name='status_korekty',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bpp.Status_Korekty'),
        ),
        migrations.AlterField(
            model_name='praca_doktorska',
            name='status_korekty',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bpp.Status_Korekty'),
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='status_korekty',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bpp.Status_Korekty'),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='status_korekty',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bpp.Status_Korekty'),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='status_korekty',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bpp.Status_Korekty'),
        ),
    ]
