# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0062_auto_20161119_2207'),
    ]

    operations = [
        migrations.AddField(
            model_name='autor',
            name='aktualny',
            field=models.BooleanField(default=False, help_text=b'Je\xc5\xbceli zaznaczone, pole to oznacza,\n    \xc5\xbce autor jest aktualnie - na dzi\xc5\x9b dzie\xc5\x84 - przypisany do jakiej\xc5\x9b jednostki w bazie danych i jego przypisanie\n    do tej jednostki nie zosta\xc5\x82o zako\xc5\x84czone wraz z konkretn\xc4\x85 dat\xc4\x85 w przesz\xc5\x82o\xc5\x9bci.', verbose_name=b'Aktualny?'),
        ),
    ]
