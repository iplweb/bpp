# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0040_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='wydzial',
            name='archiwalny',
            field=models.BooleanField(default=False, help_text=b"Je\xc5\xbceli to pole oznaczone jest jako 'PRAWDA', to jednostki 'dawne' - usuni\xc4\x99te\n        ze struktury uczelni, ale nadal wyst\xc4\x99puj\xc4\x85ce w bazie danych, b\xc4\x99d\xc4\x85 przypisywane do tego wydzia\xc5\x82u\n        przez automatyczne procedury integruj\xc4\x85ce dane z zewn\xc4\x99trznych system\xc3\xb3w informatycznych.\n        <br/><br/>\n        Je\xc5\xbceli wi\xc4\x99cej, ni\xc5\xbc jeden wydzia\xc5\x82 w bazie ma to pole oznaczone jako 'PRAWDA', jednostki\n        przypisywane b\xc4\x99d\xc4\x85 do wydzia\xc5\x82u o ni\xc5\xbcszym numerze unikalnego identyfikatora (ID)."),
        ),
    ]
