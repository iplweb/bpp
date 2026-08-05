"""Regresja: formularz jednostki musi zachować walidację drzewa MPTT.

Dołożenie ``JednostkaAdminForm`` (dla walidacji ROR-a) skasowało po MRO
``MPTTAdminForm``, którą ustawia ``MPTTModelAdmin``. Skutkiem było to, że
admin przyjmował rodzica będącego własnym potomkiem — czyli pętlę w drzewie
jednostek, rozjechane ``lft``/``rght``/``tree_id`` i ``get_descendants()``
kręcące się w nieskończoność.

Błąd był niewidoczny dla wszystkiego, co dotyczy CERIF-a: eksport działał,
walidator przechodził, testy CERIF-owe były zielone.
"""

import pytest
from django.contrib.admin.sites import AdminSite
from mptt.forms import MPTTAdminForm

from bpp.admin.jednostka import JednostkaAdmin, JednostkaAdminForm
from bpp.models import Jednostka


def test_formularz_dziedziczy_walidacje_mptt():
    assert issubclass(JednostkaAdminForm, MPTTAdminForm)


@pytest.mark.django_db
def test_admin_uzywa_formularza_z_walidacja_mptt(rf, admin_user):
    zadanie = rf.get("/")
    zadanie.user = admin_user

    formularz = JednostkaAdmin(Jednostka, AdminSite()).get_form(zadanie, None)

    assert issubclass(formularz, MPTTAdminForm)


@pytest.mark.django_db
def test_nie_da_sie_ustawic_potomka_jako_rodzica(rf, admin_user, uczelnia):
    """Kontrola właściwa: pętla rodzic↔dziecko ma zostać odrzucona.

    Formularz bierzemy z admina (``get_form``), a nie instancjonujemy
    ``JednostkaAdminForm`` wprost — ta klasa deklaruje ``Meta.fields =
    ["ror_id"]``, więc sama z siebie nie ma nawet pola ``parent``. Pełną
    listę pól składa dopiero ``modelform_factory`` z fieldsetów admina.
    """
    rodzic = Jednostka.objects.create(nazwa="Wydział", skrot="W", uczelnia=uczelnia)
    dziecko = Jednostka.objects.create(
        nazwa="Katedra", skrot="K", uczelnia=uczelnia, parent=rodzic
    )

    zadanie = rf.get("/")
    zadanie.user = admin_user
    klasa = JednostkaAdmin(Jednostka, AdminSite()).get_form(zadanie, rodzic)

    formularz = klasa(
        instance=rodzic,
        data={
            "nazwa": rodzic.nazwa,
            "skrot": rodzic.skrot,
            "uczelnia": uczelnia.pk,
            "parent": dziecko.pk,
            "kolejnosc": 0,
            "ror_id": "",
        },
    )

    assert not formularz.is_valid()
    assert "parent" in formularz.errors, formularz.errors
