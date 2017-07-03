# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0065_merge'),
    ]

    operations = [
        migrations.AddField(
            model_name='wydawnictwo_zwarte',
            name='calkowita_liczba_autorow',
            field=models.PositiveIntegerField(help_text=b'Je\xc5\xbceli dodajesz monografi\xc4\x99, wpisz tutaj ca\xc5\x82kowit\xc4\x85 liczb\xc4\x99\n        autor\xc3\xb3w monografii. Ta informacja zostanie u\xc5\xbcyta w eksporcie danych do PBN.', null=True, blank=True),
        ),
    ]
