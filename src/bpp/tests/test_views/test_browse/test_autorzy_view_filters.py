"""Testy filtrów AutorzyView._apply_uczelnia_filters (przeglądanie autorów).

Reguła „ukryj autorów obcych": ukryci mają być autorzy, których WSZYSTKIE
przypisania wskazują jednostki sztuczne — skonfigurowaną obca_jednostka
LUB jednostkę pk=-1 („Błędna/Obca" z konwencji starych wdrożeń).

Historyczny zapis `Q(jednostka__pk=-1) & Q(jednostka__pk=obca_id)
& Q(count__lte=2)` w exclude() dostawał OSOBNE joiny per warunek
(semantyka exclude dla relacji wielowartościowych), więc ukrywał tylko
autorów przypisanych do OBU sztucznych jednostek naraz; autor wyłącznie
w jednej z nich (np. tylko pk=-1) pozostawał widoczny — potwierdzone
czerwonym testem na starym kodzie. Nowa semantyka (decyzja 2026-06):
ukryj, gdy KAŻDE przypisanie jest sztuczne.
"""

import pytest
from django.test import RequestFactory
from model_bakery import baker

from bpp.models import Autor_Jednostka, Jednostka
from bpp.models.autor import Autor
from bpp.views.browse import AutorzyView


def _widoczni_autorzy(uczelnia):
    view = AutorzyView()
    view.request = RequestFactory().get("/autorzy/")
    view.kwargs = {}
    return set(view.get_queryset().values_list("pk", flat=True))


@pytest.fixture
def uczelnia_ukrywa_obcych(uczelnia):
    obca = baker.make(
        Jednostka, nazwa="Obca jednostka", skupia_pracownikow=False, uczelnia=uczelnia
    )
    uczelnia.obca_jednostka = obca
    uczelnia.pokazuj_autorow_obcych_w_przegladaniu_danych = False
    uczelnia.save()
    return uczelnia


def _jednostka_bledna(uczelnia):
    # Jednostka.save() z jawnym pk=-1 wpada w forced-update (hooki save);
    # tworzymy normalnie i przenumerowujemy queryset-owym update().
    j = baker.make(Jednostka, nazwa="Błędna", uczelnia=uczelnia)
    Jednostka.objects.filter(pk=j.pk).update(id=-1)
    return Jednostka.objects.get(pk=-1)


def _autor(nazwisko, *jednostki, aktualna=None):
    a = baker.make(Autor, imiona="Jan", nazwisko=nazwisko, pokazuj=True)
    for j in jednostki:
        Autor_Jednostka.objects.create(autor=a, jednostka=j)
    Autor.objects.filter(pk=a.pk).update(aktualna_jednostka=aktualna)
    return a


@pytest.mark.django_db
def test_ukryty_autor_tylko_w_jednostce_minus_jeden(uczelnia_ukrywa_obcych):
    """Autor przypisany WYŁĄCZNIE do jednostki pk=-1 ma być ukryty."""
    bledna = _jednostka_bledna(uczelnia_ukrywa_obcych)
    a = _autor("TylkoBledna", bledna, aktualna=bledna)

    assert a.pk not in _widoczni_autorzy(uczelnia_ukrywa_obcych)


@pytest.mark.django_db
def test_ukryty_autor_w_obu_sztucznych_jednostkach(uczelnia_ukrywa_obcych):
    """Autor przypisany do pk=-1 ORAZ obca_jednostka (i nic poza tym)
    ma być ukryty."""
    bledna = _jednostka_bledna(uczelnia_ukrywa_obcych)
    obca = uczelnia_ukrywa_obcych.obca_jednostka
    a = _autor("ObieSztuczne", bledna, obca, aktualna=obca)

    assert a.pk not in _widoczni_autorzy(uczelnia_ukrywa_obcych)


@pytest.mark.django_db
def test_ukryty_autor_tylko_w_obcej(uczelnia_ukrywa_obcych):
    obca = uczelnia_ukrywa_obcych.obca_jednostka
    a = _autor("TylkoObca", obca, aktualna=obca)

    assert a.pk not in _widoczni_autorzy(uczelnia_ukrywa_obcych)


@pytest.mark.django_db
def test_widoczny_autor_z_prawdziwa_jednostka(uczelnia_ukrywa_obcych, jednostka):
    a = _autor("Prawdziwy", jednostka, aktualna=jednostka)

    assert a.pk in _widoczni_autorzy(uczelnia_ukrywa_obcych)


@pytest.mark.django_db
def test_widoczny_autor_prawdziwa_plus_obca(uczelnia_ukrywa_obcych, jednostka):
    """Autor z prawdziwą jednostką + obcą NIE może zostać ukryty."""
    obca = uczelnia_ukrywa_obcych.obca_jednostka
    a = _autor("Mieszany", jednostka, obca, aktualna=jednostka)

    assert a.pk in _widoczni_autorzy(uczelnia_ukrywa_obcych)


@pytest.mark.django_db
def test_pokazuj_obcych_wylacza_filtr(uczelnia_ukrywa_obcych):
    """Z flagą pokazuj_autorow_obcych=True nikt nie jest ukrywany."""
    uczelnia_ukrywa_obcych.pokazuj_autorow_obcych_w_przegladaniu_danych = True
    uczelnia_ukrywa_obcych.save()

    obca = uczelnia_ukrywa_obcych.obca_jednostka
    a = _autor("ObcyWidoczny", obca, aktualna=obca)

    assert a.pk in _widoczni_autorzy(uczelnia_ukrywa_obcych)


@pytest.mark.django_db
def test_bez_grupowania_w_sql(uczelnia_ukrywa_obcych):
    """Filtr nie może budować GROUP BY po całej liście autorów
    (poprzednio: annotate(Count(autor_jednostka)))."""
    view = AutorzyView()
    view.request = RequestFactory().get("/autorzy/")
    view.kwargs = {}
    sql = str(view.get_queryset().query)
    assert "GROUP BY" not in sql.upper(), sql


@pytest.mark.django_db
def test_filtr_bez_prac(uczelnia_ukrywa_obcych, jednostka, standard_data, denorms):
    """pokazuj_autorow_bez_prac=False ukrywa autora bez publikacji,
    pokazuje autora z publikacją."""
    from bpp.tests.util import any_ciagle

    uczelnia_ukrywa_obcych.pokazuj_autorow_bez_prac_w_przegladaniu_danych = False
    uczelnia_ukrywa_obcych.save()

    a_z_praca = _autor("ZPraca", jednostka, aktualna=jednostka)
    a_bez_pracy = _autor("BezPracy", jednostka, aktualna=jednostka)

    wc = any_ciagle(tytul_oryginalny="Praca autora")
    wc.dodaj_autora(a_z_praca, jednostka)
    denorms.flush()

    widoczni = _widoczni_autorzy(uczelnia_ukrywa_obcych)
    assert a_z_praca.pk in widoczni
    assert a_bez_pracy.pk not in widoczni
