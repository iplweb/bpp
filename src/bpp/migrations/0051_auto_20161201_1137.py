# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0050_usun_model_historyczny'),
    ]

    operations = [
        migrations.AddField(
            model_name='patent_autor',
            name='zatrudniony',
            field=models.BooleanField(default=False, help_text=b'Pracownik jednostki podanej w afiliacji'),
        ),
        migrations.AddField(
            model_name='wydawnictwo_ciagle_autor',
            name='zatrudniony',
            field=models.BooleanField(default=False, help_text=b'Pracownik jednostki podanej w afiliacji'),
        ),
        migrations.AddField(
            model_name='wydawnictwo_zwarte_autor',
            name='zatrudniony',
            field=models.BooleanField(default=False, help_text=b'Pracownik jednostki podanej w afiliacji'),
        ),
    ]
