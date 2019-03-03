# -*- coding: utf-8 -*-


from django.db import migrations, models

def ustaw_obca_jednostka(apps, schema_editor):
    Jednostka = apps.get_model("bpp", "Jednostka")
    Uczelnia = apps.get_model("bpp", "Uczelnia")

    try:
        j = Jednostka.objects.get(nazwa="Obca jednostka")
    except Jednostka.DoesNotExist:
        return

    u = Uczelnia.objects.all().first()
    u.obca_jednostka = j
    u.save()

def ustaw_obca_jednostka_reverse(*args, **kw):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0050_usun_model_historyczny'),
    ]

    operations = [
        migrations.AddField(
            model_name='uczelnia',
            name='obca_jednostka',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='bpp.Jednostka', help_text=b'\n    Jednostka skupiaj\xc4\x85ca autor\xc3\xb3w nieindeksowanych, nie b\xc4\x99d\xc4\x85cych pracownikami uczelni. Procedury importuj\xc4\x85ce\n    dane z zewn\xc4\x99trznych system\xc3\xb3w informatycznych b\xc4\x99d\xc4\x85 przypisywa\xc4\x87 do tej jednostki osoby, kt\xc3\xb3re zako\xc5\x84czy\xc5\x82y\n    prac\xc4\x99 na uczelni. ', null=True),
        ),
        migrations.RunPython(ustaw_obca_jednostka, ustaw_obca_jednostka_reverse)
    ]
