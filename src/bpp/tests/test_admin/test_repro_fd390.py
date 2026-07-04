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

from types import SimpleNamespace

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


def _request(uczelnia, *, is_superuser=False, has_perm=True):
    """Minimalny request-stub dla has_delete_permission."""
    user = SimpleNamespace(
        is_superuser=is_superuser,
        is_active=True,
        is_staff=True,
        has_perm=lambda *a, **k: has_perm,
    )
    return SimpleNamespace(user=user, _uczelnia=uczelnia)


def test_repro_fd390_b_delete_cross_tenant_zablokowany(autor_w_dwoch_uczelniach):
    """Cross-tenant delete: nie-superuser z uczelni, która NIE jest aktualną
    uczelnią autora, nie może go usunąć (choć może edytować)."""
    autor, uczelnia_a, uczelnia_b = autor_w_dwoch_uczelniach
    aa = AutorAdmin(Autor, djadmin.site)

    # aktualna_jednostka autora należy do uczelni A (realna bije obcą — trigger).
    assert autor.aktualna_jednostka.uczelnia_id == uczelnia_a.pk

    # Panel uczelni B (obca dla tego autora) → delete zablokowany...
    assert aa.has_delete_permission(_request(uczelnia_b), autor) is False
    # ...ale własna uczelnia A (z uprawnieniem) → delete dozwolony.
    assert aa.has_delete_permission(_request(uczelnia_a), autor) is True


def test_repro_fd390_b_delete_superuser_bez_ograniczen(autor_w_dwoch_uczelniach):
    autor, _, uczelnia_b = autor_w_dwoch_uczelniach
    aa = AutorAdmin(Autor, djadmin.site)
    assert (
        aa.has_delete_permission(_request(uczelnia_b, is_superuser=True), autor) is True
    )


def test_repro_fd390_c_inline_zatrudnien_zawezony_do_uczelni(
    autor_w_dwoch_uczelniach,
):
    """Inline zatrudnień: nie-superuser widzi/edytuje tylko wpisy Autor_Jednostka
    bieżącej uczelni — nie może ruszyć wpisów cudzej uczelni na wspólnym autorze.
    """
    from bpp.admin.autor import Autor_JednostkaInline

    autor, uczelnia_a, uczelnia_b = autor_w_dwoch_uczelniach
    inline = Autor_JednostkaInline(Autor, djadmin.site)

    qs_b = inline.get_queryset(_request(uczelnia_b)).filter(autor=autor)
    assert {aj.jednostka.uczelnia_id for aj in qs_b} == {uczelnia_b.pk}

    qs_su = inline.get_queryset(_request(uczelnia_b, is_superuser=True)).filter(
        autor=autor
    )
    assert {aj.jednostka.uczelnia_id for aj in qs_su} == {uczelnia_a.pk, uczelnia_b.pk}
