# -*- coding: utf-8 -*-


from django.db import models, migrations
import bpp.fields


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0031_zrodlo_openaccess_licencja'),
    ]

    operations = [
        migrations.AddField(
            model_name='patent',
            name='public_dostep_dnia',
            field=models.DateField(help_text=b'Data wolnego dost\xc4\x99pu do strony WWW.', null=True, verbose_name=b'Dost\xc4\x99p dnia (wolny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='patent',
            name='public_www',
            field=models.URLField(max_length=2048, null=True, verbose_name=b'Adres WWW (wolny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='praca_doktorska',
            name='public_dostep_dnia',
            field=models.DateField(help_text=b'Data wolnego dost\xc4\x99pu do strony WWW.', null=True, verbose_name=b'Dost\xc4\x99p dnia (wolny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='praca_doktorska',
            name='public_www',
            field=models.URLField(max_length=2048, null=True, verbose_name=b'Adres WWW (wolny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='praca_doktorska',
            name='pubmed_id',
            field=models.BigIntegerField(help_text=b'Identyfikator PubMed (PMID)', null=True, verbose_name=b'PubMed ID', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='praca_habilitacyjna',
            name='public_dostep_dnia',
            field=models.DateField(help_text=b'Data wolnego dost\xc4\x99pu do strony WWW.', null=True, verbose_name=b'Dost\xc4\x99p dnia (wolny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='praca_habilitacyjna',
            name='public_www',
            field=models.URLField(max_length=2048, null=True, verbose_name=b'Adres WWW (wolny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='praca_habilitacyjna',
            name='pubmed_id',
            field=models.BigIntegerField(help_text=b'Identyfikator PubMed (PMID)', null=True, verbose_name=b'PubMed ID', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_ciagle',
            name='public_dostep_dnia',
            field=models.DateField(help_text=b'Data wolnego dost\xc4\x99pu do strony WWW.', null=True, verbose_name=b'Dost\xc4\x99p dnia (wolny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_ciagle',
            name='public_www',
            field=models.URLField(max_length=2048, null=True, verbose_name=b'Adres WWW (wolny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_ciagle',
            name='pubmed_id',
            field=models.BigIntegerField(help_text=b'Identyfikator PubMed (PMID)', null=True, verbose_name=b'PubMed ID', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_zwarte',
            name='public_dostep_dnia',
            field=models.DateField(help_text=b'Data wolnego dost\xc4\x99pu do strony WWW.', null=True, verbose_name=b'Dost\xc4\x99p dnia (wolny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_zwarte',
            name='public_www',
            field=models.URLField(max_length=2048, null=True, verbose_name=b'Adres WWW (wolny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_zwarte',
            name='pubmed_id',
            field=models.BigIntegerField(help_text=b'Identyfikator PubMed (PMID)', null=True, verbose_name=b'PubMed ID', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='zrodlo',
            name='doi',
            field=bpp.fields.DOIField(max_length=2048, blank=True, help_text=b'Digital Object Identifier (DOI)', null=True, verbose_name=b'DOI', db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='patent',
            name='dostep_dnia',
            field=models.DateField(help_text=b'Data dost\xc4\x99pu do strony WWW.', null=True, verbose_name=b'Dost\xc4\x99p dnia (p\xc5\x82atny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='patent',
            name='www',
            field=models.URLField(max_length=1024, null=True, verbose_name=b'Adres WWW (p\xc5\x82atny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='praca_doktorska',
            name='dostep_dnia',
            field=models.DateField(help_text=b'Data dost\xc4\x99pu do strony WWW.', null=True, verbose_name=b'Dost\xc4\x99p dnia (p\xc5\x82atny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='praca_doktorska',
            name='www',
            field=models.URLField(max_length=1024, null=True, verbose_name=b'Adres WWW (p\xc5\x82atny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='dostep_dnia',
            field=models.DateField(help_text=b'Data dost\xc4\x99pu do strony WWW.', null=True, verbose_name=b'Dost\xc4\x99p dnia (p\xc5\x82atny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='www',
            field=models.URLField(max_length=1024, null=True, verbose_name=b'Adres WWW (p\xc5\x82atny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='dostep_dnia',
            field=models.DateField(help_text=b'Data dost\xc4\x99pu do strony WWW.', null=True, verbose_name=b'Dost\xc4\x99p dnia (p\xc5\x82atny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='www',
            field=models.URLField(max_length=1024, null=True, verbose_name=b'Adres WWW (p\xc5\x82atny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='dostep_dnia',
            field=models.DateField(help_text=b'Data dost\xc4\x99pu do strony WWW.', null=True, verbose_name=b'Dost\xc4\x99p dnia (p\xc5\x82atny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='www',
            field=models.URLField(max_length=1024, null=True, verbose_name=b'Adres WWW (p\xc5\x82atny dost\xc4\x99p)', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='zrodlo',
            name='www',
            field=models.URLField(db_index=True, max_length=1024, null=True, verbose_name=b'WWW', blank=True),
            preserve_default=True,
        ),
    ]
