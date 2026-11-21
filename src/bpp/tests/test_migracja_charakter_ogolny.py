"""Migracja 0503: „Rozdział książki” → rozdział, PA/SKR → książka; wartości
ustawione ręcznie przez uczelnię zostają."""

import importlib

import pytest
from django.apps import apps

from bpp import const
from bpp.models import Charakter_Formalny

migracja = importlib.import_module(
    "bpp.migrations.0503_charakter_ogolny_rozdzialy_ksiazki"
)


@pytest.mark.django_db
def test_migracja_poprawia_charakter_ogolny():
    def cf(skrot, nazwa, ogolny):
        obj, _ = Charakter_Formalny.objects.get_or_create(
            skrot=skrot, defaults={"nazwa": nazwa}
        )
        Charakter_Formalny.objects.filter(pk=obj.pk).update(
            nazwa=nazwa, charakter_ogolny=ogolny
        )
        return obj.pk

    roz = cf("ROZ", "Rozdział książki", const.CHARAKTER_OGOLNY_KSIAZKA)
    wlasny = cf("RWK", "Rozdział w książce", const.CHARAKTER_OGOLNY_KSIAZKA)
    reczny = cf("RZX", "Rozdział – specjalny", const.CHARAKTER_OGOLNY_INNE)
    pa = cf("PA", "Podręcznik akademicki", const.CHARAKTER_OGOLNY_INNE)
    skr = cf("SKR", "Skrypt", const.CHARAKTER_OGOLNY_ARTYKUL)
    ks = cf("KS", "Książka", const.CHARAKTER_OGOLNY_KSIAZKA)

    migracja.popraw(apps, None)

    ogolny = dict(Charakter_Formalny.objects.values_list("pk", "charakter_ogolny"))
    assert ogolny[roz] == const.CHARAKTER_OGOLNY_ROZDZIAL
    assert ogolny[wlasny] == const.CHARAKTER_OGOLNY_ROZDZIAL
    assert ogolny[reczny] == const.CHARAKTER_OGOLNY_INNE  # nie z 0212 — zostaje
    assert ogolny[pa] == const.CHARAKTER_OGOLNY_KSIAZKA
    assert ogolny[skr] == const.CHARAKTER_OGOLNY_ARTYKUL  # ustawione ręcznie
    assert ogolny[ks] == const.CHARAKTER_OGOLNY_KSIAZKA
