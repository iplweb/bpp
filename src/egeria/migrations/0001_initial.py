# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0038_autor_pesel_md5'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Diff_Funkcja_Autora_Create',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('commited', models.BooleanField(default=False)),
                ('nazwa_skrot', models.CharField(max_length=512)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Diff_Funkcja_Autora_Delete',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('commited', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Diff_Jednostka_Create',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('commited', models.BooleanField(default=False)),
                ('nazwa', models.CharField(max_length=512)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Diff_Jednostka_Delete',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('commited', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Diff_Jednostka_Update',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('commited', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Diff_Tytul_Create',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('commited', models.BooleanField(default=False)),
                ('nazwa_skrot', models.CharField(max_length=512)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Diff_Tytul_Delete',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('commited', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Diff_Wydzial_Create',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('commited', models.BooleanField(default=False)),
                ('nazwa_skrot', models.CharField(max_length=512)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Diff_Wydzial_Delete',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('commited', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='EgeriaImport',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('file', models.FileField(upload_to=b'egeria_xls')),
                ('analyzed', models.BooleanField(default=False)),
                ('created_by', models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
        ),
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
        migrations.AddField(
            model_name='diff_wydzial_delete',
            name='parent',
            field=models.ForeignKey(to='egeria.EgeriaImport'),
        ),
        migrations.AddField(
            model_name='diff_wydzial_delete',
            name='reference',
            field=models.ForeignKey(to='bpp.Wydzial'),
        ),
        migrations.AddField(
            model_name='diff_wydzial_delete',
            name='row',
            field=models.ForeignKey(blank=True, to='egeria.EgeriaRow', null=True),
        ),
        migrations.AddField(
            model_name='diff_wydzial_create',
            name='parent',
            field=models.ForeignKey(to='egeria.EgeriaImport'),
        ),
        migrations.AddField(
            model_name='diff_wydzial_create',
            name='row',
            field=models.ForeignKey(blank=True, to='egeria.EgeriaRow', null=True),
        ),
        migrations.AddField(
            model_name='diff_tytul_delete',
            name='parent',
            field=models.ForeignKey(to='egeria.EgeriaImport'),
        ),
        migrations.AddField(
            model_name='diff_tytul_delete',
            name='reference',
            field=models.ForeignKey(to='bpp.Tytul'),
        ),
        migrations.AddField(
            model_name='diff_tytul_delete',
            name='row',
            field=models.ForeignKey(blank=True, to='egeria.EgeriaRow', null=True),
        ),
        migrations.AddField(
            model_name='diff_tytul_create',
            name='parent',
            field=models.ForeignKey(to='egeria.EgeriaImport'),
        ),
        migrations.AddField(
            model_name='diff_tytul_create',
            name='row',
            field=models.ForeignKey(blank=True, to='egeria.EgeriaRow', null=True),
        ),
        migrations.AddField(
            model_name='diff_jednostka_update',
            name='parent',
            field=models.ForeignKey(to='egeria.EgeriaImport'),
        ),
        migrations.AddField(
            model_name='diff_jednostka_update',
            name='reference',
            field=models.ForeignKey(to='bpp.Jednostka'),
        ),
        migrations.AddField(
            model_name='diff_jednostka_update',
            name='row',
            field=models.ForeignKey(blank=True, to='egeria.EgeriaRow', null=True),
        ),
        migrations.AddField(
            model_name='diff_jednostka_update',
            name='wydzial',
            field=models.ForeignKey(to='bpp.Wydzial'),
        ),
        migrations.AddField(
            model_name='diff_jednostka_delete',
            name='parent',
            field=models.ForeignKey(to='egeria.EgeriaImport'),
        ),
        migrations.AddField(
            model_name='diff_jednostka_delete',
            name='reference',
            field=models.ForeignKey(to='bpp.Jednostka'),
        ),
        migrations.AddField(
            model_name='diff_jednostka_delete',
            name='row',
            field=models.ForeignKey(blank=True, to='egeria.EgeriaRow', null=True),
        ),
        migrations.AddField(
            model_name='diff_jednostka_create',
            name='parent',
            field=models.ForeignKey(to='egeria.EgeriaImport'),
        ),
        migrations.AddField(
            model_name='diff_jednostka_create',
            name='row',
            field=models.ForeignKey(blank=True, to='egeria.EgeriaRow', null=True),
        ),
        migrations.AddField(
            model_name='diff_jednostka_create',
            name='wydzial',
            field=models.ForeignKey(to='bpp.Wydzial'),
        ),
        migrations.AddField(
            model_name='diff_funkcja_autora_delete',
            name='parent',
            field=models.ForeignKey(to='egeria.EgeriaImport'),
        ),
        migrations.AddField(
            model_name='diff_funkcja_autora_delete',
            name='reference',
            field=models.ForeignKey(to='bpp.Funkcja_Autora'),
        ),
        migrations.AddField(
            model_name='diff_funkcja_autora_delete',
            name='row',
            field=models.ForeignKey(blank=True, to='egeria.EgeriaRow', null=True),
        ),
        migrations.AddField(
            model_name='diff_funkcja_autora_create',
            name='parent',
            field=models.ForeignKey(to='egeria.EgeriaImport'),
        ),
        migrations.AddField(
            model_name='diff_funkcja_autora_create',
            name='row',
            field=models.ForeignKey(blank=True, to='egeria.EgeriaRow', null=True),
        ),
    ]
