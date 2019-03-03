# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Autorzy',
            fields=[
            ],
            options={
                'db_table': 'bpp_autorzy_mat',
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AutorzyView',
            fields=[
            ],
            options={
                'db_table': 'bpp_autorzy',
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Kronika_Patent_View',
            fields=[
            ],
            options={
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Kronika_Praca_Doktorska_View',
            fields=[
            ],
            options={
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Kronika_Praca_Habilitacyjna_View',
            fields=[
            ],
            options={
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Kronika_View',
            fields=[
            ],
            options={
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Kronika_Wydawnictwo_Ciagle_View',
            fields=[
            ],
            options={
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Kronika_Wydawnictwo_Zwarte_View',
            fields=[
            ],
            options={
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Rekord',
            fields=[
            ],
            options={
                'ordering': ['tytul_oryginalny_sort'],
                'db_table': 'bpp_rekord_mat',
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Sumy_Patent_View',
            fields=[
            ],
            options={
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Sumy_Praca_Doktorska_View',
            fields=[
            ],
            options={
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Sumy_Praca_Habilitacyjna_View',
            fields=[
            ],
            options={
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Sumy_View',
            fields=[
            ],
            options={
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Sumy_Wydawnictwo_Ciagle_View',
            fields=[
            ],
            options={
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Sumy_Wydawnictwo_Zwarte_View',
            fields=[
            ],
            options={
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.AlterModelOptions(
            name='autor_jednostka',
            options={'ordering': ['autor__nazwisko', 'jednostka__nazwa', 'rozpoczal_prace'], 'verbose_name': 'powi\u0105zanie autor-jednostka', 'verbose_name_plural': 'powi\u0105zania autor-jednostka'},
        ),
        migrations.AlterModelOptions(
            name='jezyk',
            options={'ordering': ['nazwa'], 'verbose_name': 'j\u0119zyk', 'verbose_name_plural': 'j\u0119zyki'},
        ),
        migrations.AlterModelOptions(
            name='patent_autor',
            options={'ordering': ('kolejnosc',), 'verbose_name': 'powi\u0105zanie autora z patentem', 'verbose_name_plural': 'powi\u0105zania autor\xf3w z patentami'},
        ),
        migrations.AlterModelOptions(
            name='plec',
            options={'verbose_name': 'p\u0142e\u0107', 'verbose_name_plural': 'p\u0142cie'},
        ),
        migrations.AlterModelOptions(
            name='publikacja_habilitacyjna',
            options={'ordering': ('kolejnosc',), 'verbose_name': 'powi\u0105zanie publikacji z habilitacj\u0105', 'verbose_name_plural': 'powi\u0105zania publikacji z habilitacj\u0105'},
        ),
        migrations.AlterModelOptions(
            name='punktacja_zrodla',
            options={'ordering': ['zrodlo__nazwa', 'rok'], 'verbose_name': 'punktacja \u017ar\xf3d\u0142a', 'verbose_name_plural': 'punktacja \u017ar\xf3d\u0142a'},
        ),
        migrations.AlterModelOptions(
            name='redakcja_zrodla',
            options={'verbose_name': 'redaktor \u017ar\xf3d\u0142a', 'verbose_name_plural': 'redaktorzy \u017ar\xf3d\u0142a'},
        ),
        migrations.AlterModelOptions(
            name='rodzaj_zrodla',
            options={'verbose_name': 'rodzaj \u017ar\xf3d\u0142a', 'verbose_name_plural': 'rodzaje \u017ar\xf3de\u0142'},
        ),
        migrations.AlterModelOptions(
            name='typ_odpowiedzialnosci',
            options={'ordering': ['nazwa'], 'verbose_name': 'typ odpowiedzialno\u015bci autora', 'verbose_name_plural': 'typy odpowiedzialno\u015bci autor\xf3w'},
        ),
        migrations.AlterModelOptions(
            name='tytul',
            options={'verbose_name': 'tytu\u0142', 'verbose_name_plural': 'tytu\u0142y'},
        ),
        migrations.AlterModelOptions(
            name='wydawnictwo_ciagle',
            options={'verbose_name': 'wydawnictwo ci\u0105g\u0142e', 'verbose_name_plural': 'wydawnictwa ci\u0105g\u0142e'},
        ),
        migrations.AlterModelOptions(
            name='wydawnictwo_ciagle_autor',
            options={'ordering': ('kolejnosc',), 'verbose_name': 'powi\u0105zanie autora z wyd. ci\u0105g\u0142ym', 'verbose_name_plural': 'powi\u0105zania autor\xf3w z wyd. ci\u0105g\u0142ymi'},
        ),
        migrations.AlterModelOptions(
            name='wydawnictwo_zwarte_autor',
            options={'ordering': ('kolejnosc',), 'verbose_name': 'powi\u0105zanie autora z wyd. zwartym', 'verbose_name_plural': 'powi\u0105zania autor\xf3w z wyd. zwartymi'},
        ),
        migrations.AlterModelOptions(
            name='wydzial',
            options={'ordering': ['kolejnosc', 'skrot'], 'verbose_name': 'wydzia\u0142', 'verbose_name_plural': 'wydzia\u0142y'},
        ),
        migrations.AlterModelOptions(
            name='zasieg_zrodla',
            options={'verbose_name': 'zasi\u0119g \u017ar\xf3d\u0142a', 'verbose_name_plural': 'zasi\u0119g \u017ar\xf3de\u0142'},
        ),
        migrations.AlterModelOptions(
            name='zrodlo',
            options={'ordering': ['nazwa'], 'verbose_name': '\u017ar\xf3d\u0142o', 'verbose_name_plural': '\u017ar\xf3d\u0142a'},
        ),
        migrations.AlterModelOptions(
            name='zrodlo_informacji',
            options={'verbose_name': '\u017ar\xf3d\u0142o informacji o bibliografii', 'verbose_name_plural': '\u017ar\xf3d\u0142a informacji o bibliografii'},
        ),
        migrations.AddField(
            model_name='zrodlo',
            name='nazwa_alternatywna',
            field=models.CharField(db_index=True, max_length=1024, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='zrodlo',
            name='skrot_nazwy_alternatywnej',
            field=models.CharField(db_index=True, max_length=512, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='autor',
            name='aktualna_jednostka',
            field=models.ForeignKey(on_delete=models.CASCADE, related_name='aktualna_jednostka', blank=True, to='bpp.Jednostka', null=True),
        ),
        migrations.AlterField(
            model_name='bppuser',
            name='groups',
            field=models.ManyToManyField(related_query_name='user', related_name='user_set', to='auth.Group', blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of his/her group.', verbose_name='groups'),
        ),
        migrations.AlterField(
            model_name='bppuser',
            name='user_permissions',
            field=models.ManyToManyField(related_query_name='user', related_name='user_set', to='auth.Permission', blank=True, help_text='Specific permissions for this user.', verbose_name='user permissions'),
        ),
        migrations.AlterField(
            model_name='zrodlo',
            name='skrot',
            field=models.CharField(max_length=512, verbose_name=b'Skr\xc3\xb3t', db_index=True),
        )
    ]
