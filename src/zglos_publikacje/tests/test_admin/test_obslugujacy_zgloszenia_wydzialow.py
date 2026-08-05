"""Faza B (#438): pole ``wydzial`` w adminie ma listować TYLKO korzenie
(``parent IS NULL``) — nie-korzeń nie jest samodzielnym „wydziałem"."""

import pytest
from django.contrib import admin
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia
from zglos_publikacje.admin.obslugujacy_zgloszenia_wydzialow import (
    Obslugujacy_Zgloszenia_WydzialowAdmin,
)
from zglos_publikacje.models import Obslugujacy_Zgloszenia_Wydzialow


@pytest.mark.django_db
def test_obslugujacy_zgloszenia_wydzialow_admin_wydzial_tylko_korzenie(rf):
    uczelnia = baker.make(Uczelnia)
    korzen = baker.make(Jednostka, uczelnia=uczelnia, parent=None)
    dziecko = baker.make(Jednostka, uczelnia=uczelnia, parent=korzen)

    admin_instance = Obslugujacy_Zgloszenia_WydzialowAdmin(
        Obslugujacy_Zgloszenia_Wydzialow, admin.site
    )
    db_field = Obslugujacy_Zgloszenia_Wydzialow._meta.get_field("wydzial")
    formfield = admin_instance.formfield_for_foreignkey(db_field, rf.get("/"))

    pks = set(formfield.queryset.values_list("pk", flat=True))
    assert korzen.pk in pks
    assert dziecko.pk not in pks
    assert str(formfield.label) == "Jednostka (i podrzędne)"
