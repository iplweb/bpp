# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0049_auto_20160920_0333'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='tytul',
            options={'ordering': ('skrot',), 'verbose_name': 'tytu\u0142', 'verbose_name_plural': 'tytu\u0142y'},
        ),
        migrations.RemoveField(
            model_name='jednostka',
            name='rozpoczecie_funkcjonowania',
        ),
        migrations.RemoveField(
            model_name='jednostka',
            name='zakonczenie_funkcjonowania',
        ),
        migrations.RemoveField(
            model_name='wydzial',
            name='rozpoczecie_funkcjonowania',
        ),
        migrations.RemoveField(
            model_name='wydzial',
            name='zakonczenie_funkcjonowania',
        ),
    ]
