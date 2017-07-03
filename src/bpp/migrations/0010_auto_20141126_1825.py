# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0009_auto_20141126_1804'),
    ]

    operations = [
        migrations.AlterField(
            model_name='charakter_formalny',
            name='nazwa_w_primo',
            field=models.CharField(default=b'', choices=[('', ''), ('Artyku\u0142', 'Artyku\u0142'), ('Ksi\u0105\u017cka', 'Ksi\u0105\u017cka'), ('Zas\xf3b tekstowy', 'Zas\xf3b tekstowy'), ('Rozprawa naukowa', 'Rozprawa naukowa'), ('Recenzja', 'Recenzja'), ('Artyku\u0142 prasowy', 'Artyku\u0142 prasowy'), ('Rozdzia\u0142', 'Rozdzia\u0142'), ('Czasopismo', 'Czasopismo'), ('Dane badawcze', 'Dane badawcze'), ('Materia\u0142 konferencyjny', 'Materia\u0142 konferencyjny'), ('Obraz', 'Obraz'), ('Baza', 'Baza'), ('Zestaw danych statystycznych', 'Zestaw danych statystycznych'), ('Multimedia', 'Multimedia'), ('Inny', 'Inny')], max_length=100, blank=True, help_text=b'\n    Nazwa charakteru formalnego w wyszukiwarce Primo, eksponowana przez OAI-PMH. W przypadku,\n    gdy to pole jest puste, prace o danym charakterze formalnym nie b\xc4\x99d\xc4\x85 udost\xc4\x99pniane przez\n    protok\xc3\xb3\xc5\x82 OAI-PMH.\n    ', verbose_name=b'Nazwa w Primo', db_index=True),
            preserve_default=True,
        ),
    ]
