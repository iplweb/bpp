# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

DANE_OPEN_ACCESS = """Wersja_Tekstu_OpenAccess	ORIGINAL_AUTHOR	Oryginalna wersja autorska
Wersja_Tekstu_OpenAccess	FINAL_AUTHOR	Ostateczna wersja autorska
Wersja_Tekstu_OpenAccess	FINAL_PUBLISHED	Ostateczna wersja opublikowana
Licencja_OpenAccess	CC-BY	Creative Commons - Uznanie Autorstwa (CC-BY)
Licencja_OpenAccess	CC-BY-SA	Creative Commons - Uznanie Autorstwa - Na Tych Samych Warunkach (CC-BY-SA)
Licencja_OpenAccess	CC-BY-NC	Creative Commons - Uznanie Autorstwa - Użycie niekomercyjne (CC-BY-NC);
Licencja_OpenAccess	CC-BY-ND	Creative Commons - Uznanie Autorstwa - Bez utworów zależnych (CC-BY-ND)
Licencja_OpenAccess	CC-BY-NC-SA	Creative Commons - Uznanie Autorstwa - Użycie niekomercyjne - Na tych samych warunkach (CC-BY-NC-SA)
Licencja_OpenAccess	CC-BY-NC-ND	Creative Commons - Uznanie Autorstwa - Użycie niekomercyjne - Bez utworów zależnych (CC-BY-NC-ND)
Licencja_OpenAccess	OTHER	inna otwarta licencja
Czas_Udostepnienia_OpenAccess	BEFORE_PUBLICATION	przed opublikowaniem
Czas_Udostepnienia_OpenAccess	AT_PUBLICATION	w momencie opublikowania
Czas_Udostepnienia_OpenAccess	AFTER_PUBLICATION	po opublikowaniu
Tryb_OpenAccess_Wydawnictwo_Ciagle	OPEN_JOURNAL	Otwarte czasopismo
Tryb_OpenAccess_Wydawnictwo_Ciagle	OPEN_REPOSITORY	Otwarte repositorium
Tryb_OpenAccess_Wydawnictwo_Ciagle	OTHER	Inne
Tryb_OpenAccess_Wydawnictwo_Zwarte	PUBLISHER_WEBSITE	Witryna wydawcy
Tryb_OpenAccess_Wydawnictwo_Zwarte	OPEN_REPOSITORY	Otwarte repositorium
Tryb_OpenAccess_Wydawnictwo_Zwarte	OTHER	Inne"""


def utworz_dane_openaccess(apps, schema_editor):
    for model, skrot, nazwa in [x.split('\t') for x in DANE_OPEN_ACCESS.split("\n")]:
        klass = apps.get_model('bpp', model)
        klass.objects.get_or_create(nazwa=nazwa, skrot=skrot)


def wyrzuc_dane_openaccess(apps, schema_editor):
    for model, skrot, nazwa in DANE_OPEN_ACCESS.split("\n").split("\t"):
        klass = apps.get_model('bpp', model)
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
