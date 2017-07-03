# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0037_auto_20160124_1336'),
    ]

    operations = [
        migrations.AddField(
            model_name='autor',
            name='pesel_md5',
            field=models.CharField(help_text=b'Hash MD5 numeru PESEL', max_length=32, null=True, db_index=True, blank=True),
        ),
    ]
