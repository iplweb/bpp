# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('egeria', '0004_auto_20160919_1100'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='diff_autor_delete',
            options={'ordering': ('reference__nazwisko', 'reference__imiona', 'reference__jednostka')},
        ),
    ]
