# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0056_jednostka_trigger_jednostka_wydzial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='jednostka',
            name='wydzial',
            field=models.ForeignKey(on_delete=models.CASCADE, verbose_name=b'Wydzia\xc5\x82', blank=True, to='bpp.Wydzial', null=True),
        ),
    ]
