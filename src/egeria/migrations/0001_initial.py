# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EgeriaImport',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created_on', models.DateTimeField(auto_created=True)),
                ('file', models.FileField(upload_to=b'egeria_xls')),
                ('created_by', models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='EgeriaXLS',
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
    ]
