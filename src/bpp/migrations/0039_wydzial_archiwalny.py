# -*- coding: utf-8 -*-


from django.db import migrations, models


def forwards_func(apps, schema_editor):
    # We get the model from the versioned app registry;
    # if we directly import it, it'll be the wrong version
    Wydzial = apps.get_model("bpp", "Wydzial")
    try:
        jd = Wydzial.objects.get(skrot="JD")
    except Wydzial.DoesNotExist:
        return
    jd.archiwalny = True
    jd.save()


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0038_auto_20160708_0732'),
    ]

    operations = [
        migrations.AddField(
            model_name='wydzial',
            name='archiwalny',
            field=models.BooleanField(default=False, help_text=b"Je\xc5\xbceli to pole oznaczone jest jako 'PRAWDA', to jednostki 'dawne' - usuni\xc4\x99te\n        ze struktury uczelni, ale nadal wyst\xc4\x99puj\xc4\x85ce w bazie danych, b\xc4\x99d\xc4\x85 przypisywane do tego wydzia\xc5\x82u\n        przez automatyczne procedury integruj\xc4\x85ce dane z zewn\xc4\x99trznych system\xc3\xb3w informatycznych.\n        <p/>\n        Je\xc5\xbceli wi\xc4\x99cej, ni\xc5\xbc jeden wydzia\xc5\x82 w bazie ma to pole oznaczone jako 'PRAWDA', jednostki\n        przypisywane b\xc4\x99d\xc4\x85 do wydzia\xc5\x82u o ni\xc5\xbcszym numerze unikalnego identyfikatora (ID)."),
        ),

        migrations.RunPython(forwards_func)
    ]
