# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0024_auto_20150830_1705'),
    ]

    operations = [
        migrations.AlterField(
            model_name='charakter_formalny',
            name='artykul_pbn',
            field=models.BooleanField(default=False, help_text=b'Wydawnictwa ci\xc4\x85g\xc5\x82e posiadaj\xc4\x85ce\n     ten charakter formalny zostan\xc4\x85 w\xc5\x82\xc4\x85czone do eksportu PBN jako artyku\xc5\x82y', verbose_name=b'Artyku\xc5\x82 w PBN'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='charakter_formalny',
            name='charakter_pbn',
            field=models.ForeignKey(on_delete=models.CASCADE, default=None, to='bpp.Charakter_PBN', blank=True, help_text=b'Warto\xc5\x9b\xc4\x87 wybrana w tym polu zostanie u\xc5\xbcyta jako zawarto\xc5\x9b\xc4\x87 tagu <is>\n                                      w plikach eksportu do PBN', null=True, verbose_name=b'Charakter PBN'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='charakter_formalny',
            name='ksiazka_pbn',
            field=models.BooleanField(default=False, help_text=b'Wydawnictwa zwarte posiadaj\xc4\x85ce ten\n    charakter formalny zostan\xc4\x85 w\xc5\x82\xc4\x85czone do eksportu PBN jako ksia\xc5\xbcki', verbose_name=b'Ksi\xc4\x85\xc5\xbcka w PBN'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='charakter_formalny',
            name='rozdzial_pbn',
            field=models.BooleanField(default=False, help_text=b'Wydawnictwa zwarte posiadaj\xc4\x85ce ten\n    charakter formalny zostan\xc4\x85 w\xc5\x82\xc4\x85czone do eksportu PBN jako rozdzia\xc5\x82y', verbose_name=b'Rozdzia\xc5\x82 w PBN'),
            preserve_default=True,
        ),
    ]
