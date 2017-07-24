# -*- coding: utf-8 -*-


from django.db import models, migrations

from bpp.fixtures import get_openaccess_data


def utworz_dane_openaccess(apps, schema_editor):
    for model_name, skrot, nazwa in get_openaccess_data():
        klass = apps.get_model('bpp', model_name)
        klass.objects.get_or_create(nazwa=nazwa, skrot=skrot)


def wyrzuc_dane_openaccess(apps, schema_editor):
    for model_name, skrot, nazwa in get_openaccess_data():
        klass = apps.get_model('bpp', model_name)
        klass.get(skrot=skrot).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('bpp', '0027_auto_20150921_2304'),
    ]

    operations = [
        migrations.CreateModel(
            name='Czas_Udostepnienia_OpenAccess',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('nazwa', models.CharField(unique=True, max_length=512)),
                ('skrot', models.CharField(unique=True, max_length=128)),
            ],
            options={
                'ordering': ['nazwa'],
                'verbose_name': 'czas udost\u0119pnienia OpenAccess',
                'verbose_name_plural': 'czasy udost\u0119pnienia OpenAccess',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Licencja_OpenAccess',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('nazwa', models.CharField(unique=True, max_length=512)),
                ('skrot', models.CharField(unique=True, max_length=128)),
            ],
            options={
                'ordering': ['nazwa'],
                'verbose_name': 'licencja OpenAccess',
                'verbose_name_plural': 'licencja OpenAccess',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Tryb_OpenAccess_Wydawnictwo_Ciagle',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('nazwa', models.CharField(unique=True, max_length=512)),
                ('skrot', models.CharField(unique=True, max_length=128)),
            ],
            options={
                'ordering': ['nazwa'],
                'verbose_name': 'tryb OpenAccess wyd. ci\u0105g\u0142ych',
                'verbose_name_plural': 'tryby OpenAccess wyd. ci\u0105g\u0142ych',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Tryb_OpenAccess_Wydawnictwo_Zwarte',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('nazwa', models.CharField(unique=True, max_length=512)),
                ('skrot', models.CharField(unique=True, max_length=128)),
            ],
            options={
                'ordering': ['nazwa'],
                'verbose_name': 'tryb OpenAccess wyd. zwartych',
                'verbose_name_plural': 'tryby OpenAccess wyd. zwartych',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Wersja_Tekstu_OpenAccess',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('nazwa', models.CharField(unique=True, max_length=512)),
                ('skrot', models.CharField(unique=True, max_length=128)),
            ],
            options={
                'ordering': ['nazwa'],
                'verbose_name': 'wersja tekstu OpenAccess',
                'verbose_name_plural': 'wersje tekstu OpenAccess',
            },
            bases=(models.Model,),
        ),
        migrations.AlterField(
            model_name='autor',
            name='pbn_id',
            field=models.IntegerField(null=True, blank=True,
                                      help_text=b'Identyfikator w systemie Polskiej Bibliografii Naukowej (PBN)',
                                      unique=True, verbose_name=b'Identyfikator PBN', db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='jednostka',
            name='pbn_id',
            field=models.IntegerField(null=True, blank=True,
                                      help_text=b'Identyfikator w systemie Polskiej Bibliografii Naukowej (PBN)',
                                      unique=True, verbose_name=b'Identyfikator PBN', db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='uczelnia',
            name='pbn_id',
            field=models.IntegerField(null=True, blank=True,
                                      help_text=b'Identyfikator w systemie Polskiej Bibliografii Naukowej (PBN)',
                                      unique=True, verbose_name=b'Identyfikator PBN', db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydzial',
            name='pbn_id',
            field=models.IntegerField(null=True, blank=True,
                                      help_text=b'Identyfikator w systemie Polskiej Bibliografii Naukowej (PBN)',
                                      unique=True, verbose_name=b'Identyfikator PBN', db_index=True),
            preserve_default=True,
        ),
        migrations.RunPython(
            utworz_dane_openaccess, wyrzuc_dane_openaccess
        )
    ]
