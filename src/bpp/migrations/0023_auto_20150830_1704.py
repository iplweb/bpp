# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0022_auto_20150825_2303'),
    ]

    operations = [
        migrations.AddField(
            model_name='charakter_formalny',
            name='artykul_pbn',
            field=models.BooleanField(default=False, help_text=b'Ten charakter formalny zostanie\n    wyeksportowany do PBN jako artyku\xc5\x82', verbose_name=b'Artyku\xc5\x82 w PBN'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='charakter_formalny',
            name='ksiazka_pbn',
            field=models.BooleanField(default=False, help_text=b'Ten charakter formalny zostanie\n    wyeksportowany do PBN jako ksi\xc4\x85\xc5\xbcka', verbose_name=b'Ksi\xc4\x85\xc5\xbcka w PBN'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='charakter_formalny',
            name='rozdzial_pbn',
            field=models.BooleanField(default=False, help_text=b'Ten charakter formalny zostanie\n    wyeksportowany do PBN jako rozdzia\xc5\x82.', verbose_name=b'Rozdzia\xc5\x82 w PBN'),
            preserve_default=True,
        ),
    ]
