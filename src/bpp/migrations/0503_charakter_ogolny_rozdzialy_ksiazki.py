"""Poprawka charakteru ogólnego w słowniku charakterów formalnych.

Migracja 0212 zgadywała charakter ogólny po nazwie i sprawdzała „książ”
PRZED „rozdzia” — „Rozdział książki” (i każdy „Rozdział … książki”) dostał
charakter ogólny „książka”. Do tego „Podręcznik akademicki” i „Skrypt”
zostały „inne”, choć to książki.

Ruszamy tylko wartości, które nadal są takie, jakie zostawiła 0212 — jeśli
uczelnia sama ustawiła charakter ogólny inaczej, zostaje. Charakter ogólny
wpływa na opis bibliograficzny — triggery denorm na ``bpp_charakter_formalny``
oznaczą rekordy tych charakterów do przeliczenia opisów.
"""

from django.db import migrations

KSIAZKA = "ksi"
ROZDZIAL = "roz"
INNE = "xxx"

#: Skróty książek, które 0212 zostawiła jako „inne”.
KSIAZKI = ("PA", "SKR")


def popraw(apps, schema_editor):
    Charakter_Formalny = apps.get_model("bpp", "Charakter_Formalny")
    Charakter_Formalny.objects.filter(
        nazwa__istartswith="rozdział", charakter_ogolny=KSIAZKA
    ).update(charakter_ogolny=ROZDZIAL)
    Charakter_Formalny.objects.filter(skrot__in=KSIAZKI, charakter_ogolny=INNE).update(
        charakter_ogolny=KSIAZKA
    )


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0502_autoreksporttask_xlsx"),
    ]

    operations = [
        migrations.RunPython(popraw, migrations.RunPython.noop),
    ]
