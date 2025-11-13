"""Testy weryfikujące że akcje AutorAdmin działają poprawnie z filtrami HTMX."""
import pytest
from model_bakery import baker

from bpp.models import Autor


@pytest.mark.django_db
def test_action_with_filters_in_get_params_select_across(admin_client):
    """Test weryfikujący że akcja z select_across używa filtrów z GET parameters.

    Symuluje sytuację gdy:
    1. Użytkownik zastosował filtry HTMX (które zaktualizowały URL dzięki hx-push-url="true")
    2. URL zawiera parametry filtrowania w GET (np. ?pokazuj__exact=0)
    3. Użytkownik klika "Select all X records" (select_across=1)
    4. Wykonuje akcję

    Oczekiwany rezultat: Akcja działa tylko na odfiltrowanych rekordach, nie na wszystkich.
    """
    # Przygotuj dane testowe
    # 10 autorów z pokazuj=False
    autorzy_niewidoczni = baker.make(Autor, pokazuj=False, _quantity=10)

    # 5 autorów z pokazuj=True
    autorzy_widoczni = baker.make(Autor, pokazuj=True, _quantity=5)

    # Razem: 15 autorów (10 niewidocznych, 5 widocznych)
    assert Autor.objects.count() == 15
    assert Autor.objects.filter(pokazuj=False).count() == 10
    assert Autor.objects.filter(pokazuj=True).count() == 5

    # Symuluj POST request z akcją + parametry GET z filtrami
    # To jest kluczowe: parametry filtrowania są w GET (dzięki hx-push-url="true")
    # W prawdziwym scenariuszu użytkownik zaznacza najpierw kilka elementów na bieżącej stronie,
    # a potem klika "Select all X records". Django wymaga przynajmniej jednego ID w _selected_action.
    response = admin_client.post(
        "/admin/bpp/autor/?pokazuj__exact=0",  # <-- Filtr w GET params!
        data={
            "action": "ustaw_pokazuj_true",
            "select_across": "1",  # <-- "Select all" clicked
            "_selected_action": [str(autorzy_niewidoczni[0].pk)],  # Pierwszy zaznaczony autor
        },
        follow=False,
    )

    # WERYFIKACJA: Tylko autorzy z pokazuj=False powinni być zmienieni na pokazuj=True
    # To znaczy: wszystkie 15 autorów powinno mieć pokazuj=True
    assert Autor.objects.filter(pokazuj=True).count() == 15
    assert Autor.objects.filter(pokazuj=False).count() == 0


@pytest.mark.django_db
def test_action_without_filters_select_across(admin_client):
    """Test weryfikujący że akcja bez filtrów działa na wszystkich rekordach."""
    # Przygotuj dane testowe
    autorzy = baker.make(Autor, pokazuj=False, _quantity=20)

    assert Autor.objects.count() == 20
    assert Autor.objects.filter(pokazuj=False).count() == 20

    # Request bez filtrów w GET
    # Django wymaga przynajmniej jednego ID w _selected_action przy użyciu select_across
    response = admin_client.post(
        "/admin/bpp/autor/",  # <-- Brak filtrów w GET!
        data={
            "action": "ustaw_pokazuj_true",
            "select_across": "1",
            "_selected_action": [str(autorzy[0].pk)],  # Pierwszy zaznaczony autor
        },
        follow=False,
    )

    # WERYFIKACJA: Wszystkie 20 autorów powinno być zmienionych
    assert Autor.objects.filter(pokazuj=True).count() == 20
    assert Autor.objects.filter(pokazuj=False).count() == 0


@pytest.mark.django_db
def test_action_with_multiple_filters(admin_client):
    """Test z wieloma filtrami jednocześnie (pokazuj + jednostka)."""
    # Jednostka A - 8 autorów niewidocznych
    jednostka_a = baker.make("bpp.Jednostka", nazwa="Jednostka A")
    autorzy_a_niewidoczni = baker.make(
        Autor, aktualna_jednostka=jednostka_a, pokazuj=False, _quantity=8
    )

    # Jednostka A - 2 autorów widocznych
    autorzy_a_widoczni = baker.make(
        Autor, aktualna_jednostka=jednostka_a, pokazuj=True, _quantity=2
    )

    # Jednostka B - 5 autorów niewidocznych
    jednostka_b = baker.make("bpp.Jednostka", nazwa="Jednostka B")
    autorzy_b_niewidoczni = baker.make(
        Autor, aktualna_jednostka=jednostka_b, pokazuj=False, _quantity=5
    )

    # Razem: 15 autorów (13 niewidocznych, 2 widocznych)
    assert Autor.objects.count() == 15

    # Request z dwoma filtrami: pokazuj=False AND jednostka=A
    # Django wymaga przynajmniej jednego ID w _selected_action przy użyciu select_across
    response = admin_client.post(
        f"/admin/bpp/autor/?pokazuj__exact=0&aktualna_jednostka__id__exact={jednostka_a.pk}",
        data={
            "action": "ustaw_pokazuj_true",
            "select_across": "1",
            "_selected_action": [str(autorzy_a_niewidoczni[0].pk)],  # Pierwszy zaznaczony autor
        },
        follow=False,
    )

    # WERYFIKACJA: Tylko 8 autorów z Jednostki A (pokazuj=False) powinno być zmienionych
    assert (
        Autor.objects.filter(aktualna_jednostka=jednostka_a, pokazuj=True).count() == 10
    )  # 8 zmienionych + 2 już widocznych
    assert Autor.objects.filter(aktualna_jednostka=jednostka_a, pokazuj=False).count() == 0

    # WERYFIKACJA: Autorzy z Jednostki B nadal niewidoczni
    assert Autor.objects.filter(aktualna_jednostka=jednostka_b, pokazuj=False).count() == 5
    assert Autor.objects.filter(aktualna_jednostka=jednostka_b, pokazuj=True).count() == 0

    # WERYFIKACJA: W sumie 10 widocznych (2 z początku + 8 zmienionych)
    assert Autor.objects.filter(pokazuj=True).count() == 10
