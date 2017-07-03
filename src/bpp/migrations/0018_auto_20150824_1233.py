# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0017_typy_pbn'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='bppuser',
            options={'verbose_name': 'u\u017cytkownik', 'verbose_name_plural': 'u\u017cytkownicy'},
        ),
    ]
