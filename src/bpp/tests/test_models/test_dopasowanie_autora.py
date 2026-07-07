"""Testy ``BppUser.sprobuj_dopasowac_autora`` — guard kolizji + scope uczelni.

Dwa wymagania (multi-hosted, jedna baza / wiele Uczelni):

1. **Nie nadpisuj zajętego profilu** — autor już powiązany z innym kontem
   (``OneToOne`` ``BppUser.autor``) NIE może zostać dopasowany do kolejnego
   konta. Wcześniej brak guardu powodował ``IntegrityError`` (traceback) na
   unikalnym ``autor_id``.
2. **Scope po uczelni** — dopasowujemy tylko autorów z uczelni, do której
   konto ma uprawnienia (``accessible_uczelnie`` → ``aktualna_jednostka.
   uczelnia``). Puste ``accessible_uczelnie`` = brak ograniczenia
   (kompatybilność wsteczna single-install).
"""

import pytest
from model_bakery import baker


def _autor_w_uczelni(uczelnia, **kwargs):
    jednostka = baker.make("bpp.Jednostka", uczelnia=uczelnia)
    return baker.make("bpp.Autor", aktualna_jednostka=jednostka, **kwargs)


@pytest.mark.django_db
def test_pomija_autora_z_przypisanym_userem():
    # Autor już zajęty przez inne konto — kolejne konto o tym samym e-mailu
    # NIE może go przejąć (i nie wolno rzucić IntegrityError).
    uczelnia = baker.make("bpp.Uczelnia")
    autor = _autor_w_uczelni(uczelnia, email="jan@uafm.edu.pl")
    baker.make("bpp.BppUser", autor=autor, username="pierwszy")

    drugi = baker.make("bpp.BppUser", username="drugi", email="jan@uafm.edu.pl")
    drugi.accessible_uczelnie.add(uczelnia)

    drugi.sprobuj_dopasowac_autora()  # nie może rzucić wyjątku

    drugi.refresh_from_db()
    assert drugi.autor_id is None


@pytest.mark.django_db
def test_dopasowuje_autora_w_uczelni_z_uprawnieniem():
    uczelnia = baker.make("bpp.Uczelnia")
    autor = _autor_w_uczelni(uczelnia, email="jan@uafm.edu.pl")

    user = baker.make("bpp.BppUser", email="jan@uafm.edu.pl")
    user.accessible_uczelnie.add(uczelnia)

    user.sprobuj_dopasowac_autora()

    user.refresh_from_db()
    assert user.autor_id == autor.pk


@pytest.mark.django_db
def test_nie_dopasowuje_autora_z_obcej_uczelni():
    # Autor istnieje tylko w uczelni B, a konto ma uprawnienia do A → brak
    # dopasowania (scope po uczelni).
    uczelnia_a = baker.make("bpp.Uczelnia")
    uczelnia_b = baker.make("bpp.Uczelnia")
    _autor_w_uczelni(uczelnia_b, email="jan@uafm.edu.pl")

    user = baker.make("bpp.BppUser", email="jan@uafm.edu.pl")
    user.accessible_uczelnie.add(uczelnia_a)

    user.sprobuj_dopasowac_autora()

    user.refresh_from_db()
    assert user.autor_id is None


@pytest.mark.django_db
def test_scope_rozroznia_autorow_o_tym_samym_emailu():
    # Ten sam e-mail w dwóch uczelniach — scope wybiera tego z uczelni konta
    # (bez scope byłby count()==2 i żadnego dopasowania).
    uczelnia_a = baker.make("bpp.Uczelnia")
    uczelnia_b = baker.make("bpp.Uczelnia")
    autor_a = _autor_w_uczelni(uczelnia_a, email="jan@uafm.edu.pl")
    _autor_w_uczelni(uczelnia_b, email="jan@uafm.edu.pl")

    user = baker.make("bpp.BppUser", email="jan@uafm.edu.pl")
    user.accessible_uczelnie.add(uczelnia_a)

    user.sprobuj_dopasowac_autora()

    user.refresh_from_db()
    assert user.autor_id == autor_a.pk


@pytest.mark.django_db
def test_bez_accessible_uczelnie_dopasowuje_globalnie():
    # Kompatybilność wsteczna: puste accessible_uczelnie = bez ograniczenia.
    uczelnia = baker.make("bpp.Uczelnia")
    autor = _autor_w_uczelni(uczelnia, email="jan@uafm.edu.pl")

    user = baker.make("bpp.BppUser", email="jan@uafm.edu.pl")

    user.sprobuj_dopasowac_autora()

    user.refresh_from_db()
    assert user.autor_id == autor.pk


@pytest.mark.django_db
def test_dopasowanie_po_imieniu_nazwisku_scope():
    # Brak dopasowania po e-mailu → fallback po imieniu+nazwisku, też scope.
    uczelnia = baker.make("bpp.Uczelnia")
    autor = _autor_w_uczelni(uczelnia, imiona="Przemysław", nazwisko="Kowalczewski")

    user = baker.make(
        "bpp.BppUser",
        email="",
        first_name="Przemysław",
        last_name="Kowalczewski",
    )
    user.accessible_uczelnie.add(uczelnia)

    user.sprobuj_dopasowac_autora()

    user.refresh_from_db()
    assert user.autor_id == autor.pk


@pytest.mark.django_db
def test_po_imieniu_nazwisku_pomija_zajetego():
    # Fallback po nazwisku też respektuje guard user__isnull=True.
    uczelnia = baker.make("bpp.Uczelnia")
    autor = _autor_w_uczelni(uczelnia, imiona="Przemysław", nazwisko="Kowalczewski")
    baker.make("bpp.BppUser", autor=autor, username="pierwszy")

    user = baker.make(
        "bpp.BppUser",
        username="drugi",
        email="",
        first_name="Przemysław",
        last_name="Kowalczewski",
    )
    user.accessible_uczelnie.add(uczelnia)

    user.sprobuj_dopasowac_autora()  # bez wyjątku

    user.refresh_from_db()
    assert user.autor_id is None
