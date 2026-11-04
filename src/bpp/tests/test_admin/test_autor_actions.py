"""Testy dla akcji w AutorAdmin.

„Widoczny/ukryty” = ``pokazuj_na_stronie_jednostki`` + ``pokazuj_w_rankingu``
(następczynie dawnego ``Autor.pokazuj``).
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from model_bakery import baker

from bpp.admin.autor import AutorAdmin
from bpp.models import Autor


@pytest.fixture
def mock_request(admin_user):
    """Fixture tworzący mock request dla testów admin."""
    from django.contrib.messages.storage.fallback import FallbackStorage

    factory = RequestFactory()
    request = factory.get("/admin/bpp/autor/")
    request.user = admin_user

    # Dodaj cached_groups aby uniknąć błędów w mixinach
    request.user.cached_groups = list(request.user.groups.all())

    # Dodaj message storage aby akcje mogły dodawać komunikaty
    request.session = {}
    request._messages = FallbackStorage(request)

    return request


@pytest.fixture
def autor_admin():
    """Fixture tworzący instancję AutorAdmin."""
    site = AdminSite()
    return AutorAdmin(Autor, site)


@pytest.mark.django_db
def test_ustaw_pokazuj_true_respects_queryset_filter(mock_request, autor_admin):
    """Test weryfikujący czy akcja ustaw_pokazuj_true używa tylko otrzymanego queryset.

    Symuluje sytuację gdy użytkownik:
    1. Filtruje listę autorów (np. po jednostce)
    2. Zaznacza "wszystkie odfiltrowane"
    3. Wykonuje akcję "zaznacz jako widoczny"

    Oczekiwany rezultat: zmienione są tylko autorzy z odfiltrowanego queryset.
    """
    # Przygotuj dane testowe
    # Jednostka A - 5 autorów (wszyscy ukryci)
    jednostka_a = baker.make("bpp.Jednostka", nazwa="Jednostka A")
    baker.make(
        Autor,
        aktualna_jednostka=jednostka_a,
        pokazuj_na_stronie_jednostki=False,
        pokazuj_w_rankingu=False,
        _quantity=5,
    )

    # Jednostka B - 3 autorów (wszyscy ukryci)
    jednostka_b = baker.make("bpp.Jednostka", nazwa="Jednostka B")
    baker.make(
        Autor,
        aktualna_jednostka=jednostka_b,
        pokazuj_na_stronie_jednostki=False,
        pokazuj_w_rankingu=False,
        _quantity=3,
    )

    # Razem: 8 autorów, wszyscy ukryci
    assert Autor.objects.count() == 8
    assert (
        Autor.objects.filter(
            pokazuj_na_stronie_jednostki=False, pokazuj_w_rankingu=False
        ).count()
        == 8
    )

    # Symuluj filtrowanie: użytkownik filtruje listę aby zobaczyć tylko autorów z Jednostki A
    # Django admin przekazuje do akcji queryset z zastosowanymi filtrami
    queryset_odfiltrowany = Autor.objects.filter(aktualna_jednostka=jednostka_a)

    # Sprawdź że queryset zawiera tylko 5 autorów z Jednostki A
    assert queryset_odfiltrowany.count() == 5

    # Wykonaj akcję (to co robi Django admin gdy użytkownik klika akcję)
    from bpp.admin.actions import ustaw_pokazuj_true

    ustaw_pokazuj_true(autor_admin, mock_request, queryset_odfiltrowany)

    # WERYFIKACJA: Tylko autorzy z Jednostki A powinni być widoczni
    assert (
        Autor.objects.filter(
            aktualna_jednostka=jednostka_a,
            pokazuj_na_stronie_jednostki=True,
            pokazuj_w_rankingu=True,
        ).count()
        == 5
    )

    # WERYFIKACJA: Autorzy z Jednostki B nadal powinni być ukryci
    assert (
        Autor.objects.filter(
            aktualna_jednostka=jednostka_b,
            pokazuj_na_stronie_jednostki=False,
            pokazuj_w_rankingu=False,
        ).count()
        == 3
    )

    # WERYFIKACJA: W sumie tylko 5 autorów powinno być widocznych
    assert (
        Autor.objects.filter(
            pokazuj_na_stronie_jednostki=True, pokazuj_w_rankingu=True
        ).count()
        == 5
    )
    assert (
        Autor.objects.filter(
            pokazuj_na_stronie_jednostki=False, pokazuj_w_rankingu=False
        ).count()
        == 3
    )


@pytest.mark.django_db
def test_ustaw_pokazuj_true_skips_already_visible(mock_request, autor_admin):
    """Test weryfikujący że akcja zmienia tylko ukrytych autorów."""
    # Utwórz 10 autorów: 6 ukrytych, 4 widocznych
    baker.make(
        Autor, pokazuj_na_stronie_jednostki=False, pokazuj_w_rankingu=False, _quantity=6
    )
    baker.make(
        Autor, pokazuj_na_stronie_jednostki=True, pokazuj_w_rankingu=True, _quantity=4
    )

    # Sprawdź stan początkowy
    assert (
        Autor.objects.filter(
            pokazuj_na_stronie_jednostki=False, pokazuj_w_rankingu=False
        ).count()
        == 6
    )
    assert (
        Autor.objects.filter(
            pokazuj_na_stronie_jednostki=True, pokazuj_w_rankingu=True
        ).count()
        == 4
    )

    # Wykonaj akcję na WSZYSTKICH autorach
    queryset_wszystkich = Autor.objects.all()
    assert queryset_wszystkich.count() == 10

    from bpp.admin.actions import ustaw_pokazuj_true

    ustaw_pokazuj_true(autor_admin, mock_request, queryset_wszystkich)

    # WERYFIKACJA: Wszyscy autorzy powinni być widoczni
    assert (
        Autor.objects.filter(
            pokazuj_na_stronie_jednostki=True, pokazuj_w_rankingu=True
        ).count()
        == 10
    )
    assert (
        Autor.objects.filter(
            pokazuj_na_stronie_jednostki=False, pokazuj_w_rankingu=False
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_ustaw_pokazuj_false_respects_queryset_filter(mock_request, autor_admin):
    """Test weryfikujący czy akcja ustaw_pokazuj_false używa tylko otrzymanego queryset."""
    # Jednostka A - 5 autorów (wszyscy widoczni)
    jednostka_a = baker.make("bpp.Jednostka", nazwa="Jednostka A")
    baker.make(
        Autor,
        aktualna_jednostka=jednostka_a,
        pokazuj_na_stronie_jednostki=True,
        pokazuj_w_rankingu=True,
        _quantity=5,
    )

    # Jednostka B - 3 autorów (wszyscy widoczni)
    jednostka_b = baker.make("bpp.Jednostka", nazwa="Jednostka B")
    baker.make(
        Autor,
        aktualna_jednostka=jednostka_b,
        pokazuj_na_stronie_jednostki=True,
        pokazuj_w_rankingu=True,
        _quantity=3,
    )

    # Razem: 8 autorów, wszyscy widoczni
    assert Autor.objects.count() == 8
    assert (
        Autor.objects.filter(
            pokazuj_na_stronie_jednostki=True, pokazuj_w_rankingu=True
        ).count()
        == 8
    )

    # Symuluj filtrowanie: użytkownik filtruje listę aby zobaczyć tylko autorów z Jednostki A
    queryset_odfiltrowany = Autor.objects.filter(aktualna_jednostka=jednostka_a)

    # Wykonaj akcję
    from bpp.admin.actions import ustaw_pokazuj_false

    ustaw_pokazuj_false(autor_admin, mock_request, queryset_odfiltrowany)

    # WERYFIKACJA: Tylko autorzy z Jednostki A powinni być ukryci
    assert (
        Autor.objects.filter(
            aktualna_jednostka=jednostka_a,
            pokazuj_na_stronie_jednostki=False,
            pokazuj_w_rankingu=False,
        ).count()
        == 5
    )

    # WERYFIKACJA: Autorzy z Jednostki B nadal powinni być widoczni
    assert (
        Autor.objects.filter(
            aktualna_jednostka=jednostka_b,
            pokazuj_na_stronie_jednostki=True,
            pokazuj_w_rankingu=True,
        ).count()
        == 3
    )

    # WERYFIKACJA: W sumie tylko 3 autorów powinno być widocznych
    assert (
        Autor.objects.filter(
            pokazuj_na_stronie_jednostki=True, pokazuj_w_rankingu=True
        ).count()
        == 3
    )
    assert (
        Autor.objects.filter(
            pokazuj_na_stronie_jednostki=False, pokazuj_w_rankingu=False
        ).count()
        == 5
    )
