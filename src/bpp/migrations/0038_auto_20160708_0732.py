# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0037_auto_20160124_1336'),
    ]

    operations = [
        migrations.AddField(
            model_name='wydawnictwo_ciagle',
            name='liczba_znakow_wydawniczych',
            field=models.IntegerField(db_index=True, null=True, verbose_name=b'Liczba znak\xc3\xb3w wydawniczych', blank=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='liczba_znakow_wydawniczych',
            field=models.IntegerField(db_index=True, null=True, verbose_name=b'Liczba znak\xc3\xb3w wydawniczych', blank=True),
        ),
    ]
