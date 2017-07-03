# -*- coding: utf-8 -*-


from django.db import migrations, models
from django.db.migrations.operations.special import RunPython

from bpp.models.struktura import Jednostka

def zaktualizuj(apps, schema_editor):
    Wydzial = apps.get_model("bpp", "Wydzial")

    for elem in ['Brak wpisanego wydziału',
                 'Wydział Lekarski',
                 'Jednostki Dawne',
                 'Bez Wydziału',
                 'Poza Wydziałem']:
        try:
            elem = Wydzial.objects.get(nazwa=elem)
        except Wydzial.DoesNotExist:
            continue
        elem.wirtualny = True
        elem.save()

    try:
        elem = Wydzial.objects.get(nazwa='Jednostki Dawne')
        elem.archiwalny = True
        elem.save()
    except Wydzial.DoesNotExist:
        pass

    Jednostka = apps.get_model("bpp", "Jednostka")

    for elem in ['BŁĄD: Brak wpisanej jednostki.',
                 'Studia doktoranckie',
                 'Obca jednostka']:
        try:
            elem = Jednostka.objects.get(nazwa=elem)
        except Jednostka.DoesNotExist:
            continue
        elem.wirtualna = True
        if elem.nazwa == 'Obca jednostka':
            elem.obca_jednostka = True
        elem.save()


class Migration(migrations.Migration):
    dependencies = [
        ('bpp', '0043_auto_20160817_1151'),
    ]

    operations = [
        migrations.AddField(
            model_name='jednostka',
            name='nie_archiwizuj',
            field=models.BooleanField(default=False,
                                      help_text=b'Je\xc5\xbceli zaznaczono to pole, to przy imporcie danych\n    na temat struktury uczelni z zewn\xc4\x99trznych \xc5\xbar\xc3\xb3de\xc5\x82 ta jednostka nie b\xc4\x99dzie przenoszona do wydzia\xc5\x82u oznaczonego\n    jako archiwalny.'),
        ),

        RunPython(zaktualizuj)

    ]
