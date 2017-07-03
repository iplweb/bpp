# -*- coding: utf-8 -*-


from django.db import migrations, models

STARE_DANE = {}

def ustaw_skupia_pracownikow_zarzadzaj_automatycznie(apps, schema_editor):
    Jednostka = apps.get_model("bpp", "Jednostka")
    for j in Jednostka.objects.all():
        if STARE_DANE[j.pk]['wirtualna']:
            j.zarzadzaj_automatycznie = False
        if STARE_DANE[j.pk]['obca_jednostka']:
            j.skupia_pracownikow = False
        j.save()
    pass

def nic(apps, schema_editor):
    pass

def zapisz_tymczasowe_dane_w_zmiennej_globalnej(apps, schema_editor):
    Jednostka = apps.get_model("bpp", "Jednostka")
    for j in Jednostka.objects.all():
        STARE_DANE[j.pk] = {'wirtualna': j.wirtualna, 'obca_jednostka': j.obca_jednostka}

class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0051_uczelnia_obca_jednostka'),
    ]

    operations = [
        migrations.RunPython(
            zapisz_tymczasowe_dane_w_zmiennej_globalnej,
            nic
        ),

        migrations.AddField(
            model_name='jednostka',
            name='skupia_pracownikow',
            field=models.BooleanField(default=True, help_text=b"Ta jednostka skupia osoby b\xc4\x99d\xc4\x85ce faktycznymi pracownikami uczelni. Odznacz dla jednostek\n         typu 'Studenci', 'Doktoranci', 'Pracownicy emerytowani' itp.", verbose_name=b'Skupia pracownik\xc3\xb3w'),
        ),
        migrations.AddField(
            model_name='jednostka',
            name='zarzadzaj_automatycznie',
            field=models.BooleanField(default=True, help_text=b'Jednostka ta b\xc4\x99dzie dowolnie modyfikowana przez procedury importujace dane z zewn\xc4\x99trznych\n        system\xc3\xb3w informatycznych', verbose_name=b'Zarz\xc4\x85dzaj automatycznie'),
        ),
        migrations.RemoveField(
            model_name='jednostka',
            name='nie_archiwizuj',
        ),
        migrations.RemoveField(
            model_name='jednostka',
            name='obca_jednostka',
        ),
        migrations.RemoveField(
            model_name='jednostka',
            name='wirtualna',
        ),
        migrations.RunPython(
            ustaw_skupia_pracownikow_zarzadzaj_automatycznie,
            nic
        ),

    ]
