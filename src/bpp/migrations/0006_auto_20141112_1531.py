# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0005_auto_20141107_1950'),
    ]

    operations = [
        migrations.AddField(
            model_name='praca_doktorska',
            name='promotor',
            field=models.ForeignKey(on_delete=models.CASCADE, related_name='promotor_doktoratu', blank=True, to='bpp.Autor', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='patent',
            name='afiliowana',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AlterField(
            model_name='patent',
            name='recenzowana',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AlterField(
            model_name='praca_doktorska',
            name='afiliowana',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AlterField(
            model_name='praca_doktorska',
            name='recenzowana',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='afiliowana',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='recenzowana',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='afiliowana',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='recenzowana',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='afiliowana',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='recenzowana',
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]
