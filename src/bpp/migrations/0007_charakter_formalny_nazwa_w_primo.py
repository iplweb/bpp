# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0006_auto_20141112_1531'),
    ]

    operations = [
        migrations.AddField(
            model_name='charakter_formalny',
            name='nazwa_w_primo',
            field=models.CharField(default=b'', choices=[(b'', b''), (b'Artyku\xc5\x82', b'Artyku\xc5\x82'), (b'Ksi\xc4\x85\xc5\xbcka', b'Ksi\xc4\x85\xc5\xbcka'), (b'Zas\xc3\xb3b tekstowy', b'Zas\xc3\xb3b tekstowy'), (b'Rozprawa naukowa', b'Rozprawa naukowa'), (b'Recenzja', b'Recenzja'), (b'Artyku\xc5\x82 prasowy', b'Artyku\xc5\x82 prasowy'), (b'Rozdzia\xc5\x82', b'Rozdzia\xc5\x82'), (b'Czasopismo', b'Czasopismo'), (b'Dane badawcze', b'Dane badawcze'), (b'Materia\xc5\x82 konferencyjny', b'Materia\xc5\x82 konferencyjny'), (b'Obraz', b'Obraz'), (b'Baza', b'Baza'), (b'Zestaw danych statystycznych', b'Zestaw danych statystycznych'), (b'Multimedia', b'Multimedia'), (b'Inny', b'Inny')], max_length=100, blank=True, help_text=b'\n    Nazwa charakteru formalnego w wyszukiwarce Primo, eksponowana przez OAI-PMH. W przypadku,\n    gdy to pole jest puste, prace o danym charakterze formalnym nie b\xc4\x99d\xc4\x85 udost\xc4\x99pniane przez\n    protok\xc3\xb3\xc5\x82 OAI-PMH.\n    ', db_index=True),
            preserve_default=True,
        ),
    ]
