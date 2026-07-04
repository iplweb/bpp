"""Repro FD#390 (B) — edycja autora w adminie multi-homed.

Reguła: autor jest edytowalny w panelu danej uczelni, jeśli był KIEDYKOLWIEK
z nią związany (obecnie LUB historycznie) — nie tylko gdy jego ``aktualna_
jednostka`` należy akurat do tej uczelni.

Wspólna baza multi-homed: jeden autor bywa „aktualnie" przypisany do uczelni A
(realna jednostka), a jednocześnie ma historyczny wpis w uczelni B (np. „obca
jednostka" po imporcie publikacji B). Personel „wprowadzanie danych" uczelni B
musi móc otworzyć takiego autora do edycji — poprzednio ``SiteFilteredAdminMixin``
zawężał queryset do ``aktualna_jednostka__uczelnia`` i dawał 404.
"""

import pytest
from django.contrib import admin as djadmin
from model_bakery import baker

from bpp.admin.autor import AutorAdmin
from bpp.models import Autor, Autor_Jednostka, Jednostka, Uczelnia


@pytest.fixture
def autor_w_dwoch_uczelniach(db):
    """Autor: realna jednostka uczelni A + obca jednostka uczelni B."""
    uczelnia_a = baker.make(Uczelnia)
    uczelnia_b = baker.make(Uczelnia)
    jedn_a = baker.make(
        Jednostka, uczelnia=uczelnia_a, wydzial=None, skupia_pracownikow=True
    )
    obca_b = baker.make(
        Jednostka, uczelnia=uczelnia_b, wydzial=None, skupia_pracownikow=False
    )
    autor = baker.make(Autor)
    Autor_Jednostka.objects.create(autor=autor, jednostka=jedn_a)
    Autor_Jednostka.objects.create(autor=autor, jednostka=obca_b)
    autor.refresh_from_db()
    return autor, uczelnia_a, uczelnia_b


def test_repro_fd390_b_autor_edytowalny_w_obu_uczelniach(autor_w_dwoch_uczelniach):
    autor, uczelnia_a, uczelnia_b = autor_w_dwoch_uczelniach
    aa = AutorAdmin(Autor, djadmin.site)

    scoped_b = aa.filter_queryset_for_uczelnia(Autor.objects.all(), uczelnia_b)
    assert autor in scoped_b, (
        "Autor związany historycznie z uczelnią B musi być edytowalny "
        "w panelu B (był w niej — obca jednostka)."
    )

    scoped_a = aa.filter_queryset_for_uczelnia(Autor.objects.all(), uczelnia_a)
    assert autor in scoped_a, "Autor jest też pracownikiem uczelni A."


def test_repro_fd390_b_obcy_autor_niewidoczny(autor_w_dwoch_uczelniach):
    """Autor bez żadnego związku z uczelnią C nie wpada w jej zakres."""
    autor, _, _ = autor_w_dwoch_uczelniach
    uczelnia_c = baker.make(Uczelnia)
    aa = AutorAdmin(Autor, djadmin.site)

    scoped_c = aa.filter_queryset_for_uczelnia(Autor.objects.all(), uczelnia_c)
    assert autor not in scoped_c
