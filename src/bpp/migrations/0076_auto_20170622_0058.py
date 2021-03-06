# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-06-21 22:58


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0075_auto_20170622_0057'),
    ]

    operations = [
        migrations.AlterField(
            model_name='autor',
            name='aktualny',
            field=models.BooleanField(db_index=True, default=False, help_text=b'Je\xc5\xbceli zaznaczone, pole to oznacza,\n    \xc5\xbce autor jest aktualnie - na dzi\xc5\x9b dzie\xc5\x84 - przypisany do jakiej\xc5\x9b jednostki w bazie danych i jego przypisanie\n    do tej jednostki nie zosta\xc5\x82o zako\xc5\x84czone wraz z konkretn\xc4\x85 dat\xc4\x85 w \n    przesz\xc5\x82o\xc5\x9bci.', verbose_name=b'Aktualny?'),
        ),
    ]
