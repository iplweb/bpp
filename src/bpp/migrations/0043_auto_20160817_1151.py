# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0042_auto_20160802_2346'),
    ]

    operations = [
        migrations.AddField(
            model_name='jednostka',
            name='obca_jednostka',
            field=models.BooleanField(default=False, help_text=b'Zaznacz dla jednostki skupiaj\xc4\x85cej autor\xc3\xb3w nieindeksowanych,\n        np. dla "Obca jednostka" lub "Doktoranci".\n\n                <br/><br/>\n        Je\xc5\xbceli wi\xc4\x99cej, ni\xc5\xbc jedna jednostka w bazie danych ma to pole oznaczone jako \'PRAWDA\', autorzy\n        przypisywani b\xc4\x99d\xc4\x85 do jednostki obcej o ni\xc5\xbcszym numerze unikalnego identyfikatora (ID).\n        '),
        ),
        migrations.AddField(
            model_name='jednostka',
            name='wirtualna',
            field=models.BooleanField(default=False, help_text=b'Jednostka wirtualna to jednostka nie maj\xc4\x85ca odzwierciedlenia\n        w strukturach uczelni, utworzona jedynie na potrzeby bazy danych. Przyk\xc5\x82adowo, mo\xc5\xbce by\xc4\x87\n        to "Obca jednostka" - dla autor\xc3\xb3w nieindeksowanych, lub te\xc5\xbc mo\xc5\xbce by\xc4\x87 to jednostka "Doktoranci".\n        Tego typu jednostka musi by\xc4\x87 zarz\xc4\x85dzana r\xc4\x99cznie od strony strukturalnej - nie b\xc4\x99dzie\n        ukrywana, usuwana ani zmieniana przez procedury importuj\xc4\x85ce dane z zewn\xc4\x99trznych system\xc3\xb3w. '),
        ),
        migrations.AddField(
            model_name='wydzial',
            name='wirtualny',
            field=models.BooleanField(default=False, help_text=b'Wydzia\xc5\x82 wirtualny to wydzia\xc5\x82 nie maj\xc4\x85cy odzwierciedlenia\n        w strukturach uczelni, utworzony na potrzeby bazy danych. Przyk\xc5\x82adowo, mo\xc5\xbce by\xc4\x87\n        to wydzia\xc5\x82 skupiaj\xc4\x85cy jednostki dawne lub jednostki typu "Obca jednostka", "Doktoranci".\n        Tego typu wydzia\xc5\x82 musi by\xc4\x87 zarz\xc4\x85dzany r\xc4\x99cznie - nie b\xc4\x99dzie usuwany, ukrywany ani aktualizowany\n        przez procedury importuj\xc4\x85ce dane z zewn\xc4\x99trznych system\xc3\xb3w. '),
        ),
    ]
