# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0053_obiekt_jednostka_pole_uczelnia'),
    ]

    operations = [
        migrations.AddField(
            model_name='jednostka',
            name='aktualna',
            field=models.BooleanField(default=False, help_text=b"Je\xc5\xbceli dana jednostka wchodzi w struktury wydzia\xc5\x82u\n    (czyli jej obecno\xc5\x9b\xc4\x87 w strukturach wydzia\xc5\x82u nie zosta\xc5\x82a zako\xc5\x84czona z okre\xc5\x9blon\xc4\x85 dat\xc4\x85), to pole to b\xc4\x99dzie mia\xc5\x82o\n    warto\xc5\x9b\xc4\x87 'PRAWDA'."),
        ),
    ]
