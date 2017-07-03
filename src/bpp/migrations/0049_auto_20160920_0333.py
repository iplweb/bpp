# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0048_wyczysc_nazwy_jednostek'),
    ]

    operations = [
        migrations.AlterField(
            model_name='autor',
            name='pesel_md5',
            field=models.CharField(max_length=32, blank=True, help_text=b'Hash MD5 numeru PESEL', null=True, verbose_name=b'PESEL MD5', db_index=True),
        ),
    ]
