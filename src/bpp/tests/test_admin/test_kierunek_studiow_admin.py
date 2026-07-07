"""Faza B (#438): pole ``wydzial`` w adminie ``Kierunek_Studiow`` ma listować
TYLKO korzenie (``parent IS NULL``) — nie-korzeń nie jest samodzielnym
„wydziałem"."""

import pytest
from django.contrib import admin
from model_bakery import baker

from bpp.admin.kierunek_studiow import Kierunek_StudiowAdmin
from bpp.models import Jednostka, Kierunek_Studiow, Uczelnia


@pytest.mark.django_db
def test_kierunek_studiow_admin_wydzial_tylko_korzenie(rf):
    uczelnia = baker.make(Uczelnia)
    korzen = baker.make(Jednostka, uczelnia=uczelnia, parent=None)
    dziecko = baker.make(Jednostka, uczelnia=uczelnia, parent=korzen)

    admin_instance = Kierunek_StudiowAdmin(Kierunek_Studiow, admin.site)
    db_field = Kierunek_Studiow._meta.get_field("wydzial")
    formfield = admin_instance.formfield_for_foreignkey(db_field, rf.get("/"))

    pks = set(formfield.queryset.values_list("pk", flat=True))
    assert korzen.pk in pks
    assert dziecko.pk not in pks
