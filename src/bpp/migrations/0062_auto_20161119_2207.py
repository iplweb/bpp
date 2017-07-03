# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0061_utworz_jednostka_wydzial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='jednostka_wydzial',
            options={'ordering': ('-od',), 'verbose_name': 'powi\u0105zanie jednostka-wydzia\u0142', 'verbose_name_plural': 'powi\u0105zania jednostka-wydzia\u0142'},
        ),
    ]
