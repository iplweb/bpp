# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('bpp', '0047_merge'),
    ]

    operations = [
        migrations.CreateModel(
            name='Diff_Autor_Create',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('commited', models.BooleanField(default=False)),
                ('nazwisko', models.CharField(max_length=200)),
                ('imiona', models.CharField(max_length=200)),
                ('pesel_md5', models.CharField(max_length=32)),
                ('funkcja', models.ForeignKey(to='bpp.Funkcja_Autora')),
                ('jednostka', models.ForeignKey(to='bpp.Jednostka')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Diff_Autor_Delete',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('commited', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Diff_Autor_Update',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('commited', models.BooleanField(default=False)),
                ('nazwisko', models.CharField(max_length=200)),
                ('imiona', models.CharField(max_length=200)),
                ('pesel_md5', models.CharField(max_length=32)),
                ('funkcja', models.ForeignKey(to='bpp.Funkcja_Autora')),
                ('jednostka', models.ForeignKey(to='bpp.Jednostka')),
            ],
            options={
                'abstract': False,
            },
        ),
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
                ('file', models.FileField(upload_to=b'egeria_xls', verbose_name=b'Plik XLS')),
                ('analyzed', models.BooleanField(default=False)),
                ('analysis_level', models.IntegerField(default=0)),
                ('error', models.BooleanField(default=False)),
                ('error_message', models.TextField(null=True, blank=True)),
                ('created_by', models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ('-created_on',),
            },
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
                ('unmatched_because_new', models.BooleanField(default=False)),
                ('unmatched_because_multiple', models.BooleanField(default=False)),
                ('matched_autor', models.ForeignKey(to='bpp.Autor', null=True)),
                ('matched_funkcja', models.ForeignKey(to='bpp.Funkcja_Autora', null=True)),
                ('matched_jednostka', models.ForeignKey(to='bpp.Jednostka', null=True)),
                ('matched_tytul', models.ForeignKey(to='bpp.Tytul', null=True)),
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
        migrations.AddField(
            model_name='diff_autor_update',
            name='parent',
            field=models.ForeignKey(to='egeria.EgeriaImport'),
        ),
        migrations.AddField(
            model_name='diff_autor_update',
            name='reference',
            field=models.ForeignKey(to='bpp.Autor'),
        ),
        migrations.AddField(
            model_name='diff_autor_update',
            name='row',
            field=models.ForeignKey(blank=True, to='egeria.EgeriaRow', null=True),
        ),
        migrations.AddField(
            model_name='diff_autor_update',
            name='tytul',
            field=models.ForeignKey(blank=True, to='bpp.Tytul', null=True),
        ),
        migrations.AddField(
            model_name='diff_autor_delete',
            name='parent',
            field=models.ForeignKey(to='egeria.EgeriaImport'),
        ),
        migrations.AddField(
            model_name='diff_autor_delete',
            name='reference',
            field=models.ForeignKey(to='bpp.Autor'),
        ),
        migrations.AddField(
            model_name='diff_autor_delete',
            name='row',
            field=models.ForeignKey(blank=True, to='egeria.EgeriaRow', null=True),
        ),
        migrations.AddField(
            model_name='diff_autor_create',
            name='parent',
            field=models.ForeignKey(to='egeria.EgeriaImport'),
        ),
        migrations.AddField(
            model_name='diff_autor_create',
            name='row',
            field=models.ForeignKey(blank=True, to='egeria.EgeriaRow', null=True),
        ),
        migrations.AddField(
            model_name='diff_autor_create',
            name='tytul',
            field=models.ForeignKey(blank=True, to='bpp.Tytul', null=True),
        ),
    ]
