# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0013_wydzial_zezwalaj_na_ranking_autorow'),
    ]

    operations = [
        migrations.AlterField(
            model_name='wydzial',
            name='widoczny',
            field=models.BooleanField(default=True, help_text=b'Czy wydzia\xc5\x82 ma by\xc4\x87 widoczny przy przegl\xc4\x85daniu strony dla zak\xc5\x82adki "Uczelnia"?'),
            preserve_default=True,
        ),
    ]
