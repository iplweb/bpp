# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('egeria', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='diff_autor_create',
            options={'ordering': ('nazwisko', 'imiona', 'jednostka')},
        ),
        migrations.AlterModelOptions(
            name='diff_autor_update',
            options={'ordering': ('nazwisko', 'imiona', 'jednostka')},
        ),
    ]
