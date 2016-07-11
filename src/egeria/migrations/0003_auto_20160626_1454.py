# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('egeria', '0002_auto_20160626_1448'),
    ]

    operations = [
        migrations.CreateModel(
            name='EgeriaRow',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('lp', models.IntegerField()),
                ('tytul_stopien', models.CharField(max_length=100)),
                ('nazwisko', models.CharField(max_length=200)),
                ('imie', models.CharField(max_length=200)),
                ('pesel_md5', models.CharField(max_length=32)),
                ('stanowisko', models.CharField(max_length=50)),
                ('nazwa_jednostki', models.CharField(max_length=300)),
                ('wydzial', models.CharField(max_length=150)),
                ('parent', models.ForeignKey(to='egeria.EgeriaImport')),
            ],
        ),
        migrations.RemoveField(
            model_name='egeriaxls',
            name='parent',
        ),
        migrations.DeleteModel(
            name='EgeriaXLS',
        ),
    ]
