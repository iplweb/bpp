"""Faza B / issue #438 — I-3.

Testy uogólnienia metryczki historycznej na ``Jednostka_Rodzic``
(pole ``wydzial`` FK→Wydzial zastąpione ``parent`` FK→Jednostka), LAZY węzła-
lustra Wydzial→Jednostka (tworzonego dopiero przy linkowaniu) oraz usunięcia
walidacji równości uczelni z ``clean()`` (federacja, Zasada #4).
"""

import pytest
from model_bakery import baker

from bpp.models import Jednostka, Jednostka_Rodzic, Uczelnia, Wydzial
from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu


@pytest.mark.django_db
def test_jednostka_rodzic_ma_pole_parent_nie_ma_wydzial():
    """Model dostępny jako Jednostka_Rodzic, ma pole ``parent`` (FK Jednostka),
    NIE ma już pola ``wydzial``."""
    field_names = {f.name for f in Jednostka_Rodzic._meta.get_fields()}
    assert "parent" in field_names
    assert "wydzial" not in field_names

    parent_field = Jednostka_Rodzic._meta.get_field("parent")
    assert parent_field.related_model is Jednostka
    assert parent_field.null is True


@pytest.mark.django_db
def test_wezel_lustro_nie_powstaje_eager():
    """LAZY: samo utworzenie Wydziału NIE tworzy węzła-lustra (inaczej
    zawyżałoby Jednostka.objects.count() w każdym teście z fixture'em)."""
    u = baker.make(Uczelnia)
    w = baker.make(Wydzial, uczelnia=u)

    assert not Jednostka.objects.filter(legacy_wydzial_id=w.id).exists()


@pytest.mark.django_db
def test_znajdz_lub_utworz_wezel_tworzy_na_zadanie():
    """LAZY helper tworzy węzeł-lustro (legacy_wydzial_id == wydzial.id,
    aktualna=False) dopiero na żądanie. Po IV-1 (#438) węzeł DZIEDZICZY
    widoczność ze źródłowego ``Wydzial.widoczny`` (spójnie z odkryciem w
    migracji 0462) — tu Wydzial ma domyślnie ``widoczny=True``."""
    u = baker.make(Uczelnia)
    w = baker.make(Wydzial, uczelnia=u, widoczny=True)

    wezel, created = znajdz_lub_utworz_wezel_wydzialu(w)

    assert created is True
    assert wezel.legacy_wydzial_id == w.id
    assert wezel.widoczna is True
    assert wezel.aktualna is False
    assert wezel.uczelnia_id == u.id

    # Wydział ukryty → węzeł-lustro również ukryty.
    w_hid = baker.make(Wydzial, uczelnia=u, widoczny=False)
    wezel_hid, _ = znajdz_lub_utworz_wezel_wydzialu(w_hid)
    assert wezel_hid.widoczna is False


@pytest.mark.django_db
def test_znajdz_lub_utworz_wezel_idempotentny():
    """Drugie wywołanie helpera nie duplikuje węzła-lustra."""
    u = baker.make(Uczelnia)
    w = baker.make(Wydzial, uczelnia=u)

    first, c1 = znajdz_lub_utworz_wezel_wydzialu(w)
    second, c2 = znajdz_lub_utworz_wezel_wydzialu(w)

    assert c1 is True
    assert c2 is False
    assert first == second
    assert Jednostka.objects.filter(legacy_wydzial_id=w.id).count() == 1


@pytest.mark.django_db
def test_post_delete_wydzialu_usuwa_wezel_lustro():
    """Skasowanie Wydziału sprząta węzeł-lustro (bez sieroty)."""
    u = baker.make(Uczelnia)
    w = baker.make(Wydzial, uczelnia=u)
    znajdz_lub_utworz_wezel_wydzialu(w)
    wid = w.id

    assert Jednostka.objects.filter(legacy_wydzial_id=wid).exists()

    w.delete()

    assert not Jednostka.objects.filter(legacy_wydzial_id=wid).exists()


@pytest.mark.django_db
def test_parent_mapuje_na_stary_wydzial_przez_legacy():
    """Backfill/runtime: ``parent`` wpisu wskazuje węzeł o
    ``legacy_wydzial_id == staremu wydzial_id`` — sygnał wyprowadza z tego
    ``Jednostka.wydzial_id`` (interim, do B-III)."""
    u = baker.make(Uczelnia)
    w = baker.make(Wydzial, uczelnia=u)
    j = baker.make(Jednostka, uczelnia=u)

    wezel, _ = znajdz_lub_utworz_wezel_wydzialu(w)
    jr = Jednostka_Rodzic.objects.create(jednostka=j, parent=wezel)

    assert jr.parent.legacy_wydzial_id == w.id

    # Faza B (#438), II-1: sygnał NIE derywuje już ``wydzial`` z historii —
    # węzeł-rodzic (mirror) mapuje na stary Wydzial przez ``legacy_wydzial_id``
    # (sprawdzone wyżej); ``Jednostka.wydzial`` wylicza denorm z MPTT parent.
    j.refresh_from_db()
    assert j.aktualna is True


@pytest.mark.django_db
def test_clean_cross_uczelnia_nie_rzuca():
    """clean() bez walidacji uczelni: jednostka uczelni u1 + węzeł-rodzic
    uczelni u2 NIE rzuca ValidationError (federacja)."""
    u1 = baker.make(Uczelnia)
    u2 = baker.make(Uczelnia)
    w2 = baker.make(Wydzial, uczelnia=u2)
    j1 = baker.make(Jednostka, uczelnia=u1)

    wezel_u2, _ = znajdz_lub_utworz_wezel_wydzialu(w2)
    jr = Jednostka_Rodzic(jednostka=j1, parent=wezel_u2)

    # Nie powinno rzucić — brak walidacji równości uczelni:
    jr.clean()
