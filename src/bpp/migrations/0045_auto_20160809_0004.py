# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0044_zaktualizuj_obce_archiwalne'),
    ]

    operations = [
        migrations.AlterField(
            model_name='jednostka',
            name='obca_jednostka',
            field=models.BooleanField(default=False, help_text=b'Zaznacz dla jednostki skupiaj\xc4\x85cej autor\xc3\xb3w nieindeksowanych,\n        np. dla "Obca jednostka" lub "Doktoranci".\n\n                <br/><br/>\n        Je\xc5\xbceli wi\xc4\x99cej, ni\xc5\xbc jedna jednostka w bazie danych ma to pole oznaczone jako \'PRAWDA\', autorzy\n        przypisywani b\xc4\x99d\xc4\x85 do jednostki obcej o ni\xc5\xbcszym numerze unikalnego identyfikatora (ID).\n        '),
        ),
    ]
