"""Testy filtra „Wydział" na changeliście ``AutorAdmin`` (#438, domknięcie).

Faza B (#438) zamieniła goły ``list_filter = ("wydzial", ...)`` na
``WydzialFilter`` w ``JednostkaAdmin``, ale ``AutorAdmin`` został z gołym
stringiem ``"aktualna_jednostka__wydzial"``. Ponieważ denorm
``Jednostka.wydzial`` jest self-FK na ``Jednostka``, ``RelatedFieldListFilter``
enumerował CAŁĄ tabelę jednostek (produkcyjnie: 504 pozycje zamiast
7 wydziałów).
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.admin.filters import WydzialAutoraFilter
from bpp.models import Autor, Jednostka, Uczelnia


def _spec_wydzial(response):
    """Zwraca FilterSpec o tytule „Wydział" z wyrenderowanej changelisty."""
    for spec in response.context["cl"].filter_specs:
        if str(spec.title) == "Wydział":
            return spec
    return None


@pytest.mark.django_db
def test_AutorAdmin_WydzialFilter_opcje_tylko_korzenie(
    admin_client,
    uczelnia: Uczelnia,
    jednostka: Jednostka,
    jednostka_podrzedna: Jednostka,
    druga_jednostka: Jednostka,
):
    # ISTOTA BUGA: opcji filtra ma być tyle, ile jednostek-korzeni („wydziałów"),
    # a nie tyle, ile jednostek w bazie. Tu drzewo to 1 korzeń (fixture
    # `wydzial`) + 3 węzły niżej — więc dokładnie 1 opcja, nie 4.
    uczelnia.uzywaj_wydzialow = True
    uczelnia.save()

    response = admin_client.get(reverse("admin:bpp_autor_changelist"))
    assert response.status_code == 200

    spec = _spec_wydzial(response)
    assert spec is not None, "changelist nie renderuje filtra po wydziale"

    korzenie = Jednostka.objects.filter(parent__isnull=True, widoczna=True)
    lookup_pks = {pk for pk, _ in spec.lookup_choices}
    assert lookup_pks == {j.pk for j in korzenie}
    assert len(lookup_pks) == korzenie.count()
    # Węzły spod korzenia NIE mogą trafiać na listę wyboru „wydziału".
    assert jednostka.pk not in lookup_pks
    assert jednostka_podrzedna.pk not in lookup_pks
    assert druga_jednostka.pk not in lookup_pks


@pytest.mark.django_db
def test_AutorAdmin_WydzialFilter_filtruje_poddrzewo(
    admin_client,
    jednostka: Jednostka,
    jednostka_podrzedna: Jednostka,
    druga_jednostka: Jednostka,
):
    # Wybór korzenia zawęża do autorów z CAŁEGO poddrzewa: bezpośrednich
    # dzieci, wnuków ORAZ przypisanych wprost do korzenia (ten ostatni
    # przypadek obsługuje `| Q(aktualna_jednostka_id=v)`).
    root = jednostka.parent
    obcy_root = baker.make(Jednostka, parent=None, uczelnia=jednostka.uczelnia)
    obca = baker.make(Jednostka, parent=obcy_root, uczelnia=jednostka.uczelnia)

    a_dziecko = baker.make(Autor, aktualna_jednostka=jednostka)
    a_wnuk = baker.make(Autor, aktualna_jednostka=jednostka_podrzedna)
    a_drugie_dziecko = baker.make(Autor, aktualna_jednostka=druga_jednostka)
    a_korzen = baker.make(Autor, aktualna_jednostka=root)
    a_obcy = baker.make(Autor, aktualna_jednostka=obca)
    a_bez_jednostki = baker.make(Autor, aktualna_jednostka=None)

    response = admin_client.get(
        reverse("admin:bpp_autor_changelist"), {"wydzial": root.pk}
    )
    assert response.status_code == 200

    result_list = list(response.context["cl"].result_list)
    assert a_dziecko in result_list
    assert a_wnuk in result_list
    assert a_drugie_dziecko in result_list
    assert a_korzen in result_list
    assert a_obcy not in result_list
    assert a_bez_jednostki not in result_list


@pytest.mark.django_db
def test_AutorAdmin_WydzialFilter_ukryty_gdy_uczelnia_bez_wydzialow(
    admin_client, uczelnia: Uczelnia, jednostka: Jednostka
):
    # Bramka `uzywaj_wydzialow` (dziedziczona z WydzialFilter): instytucja
    # 1-progowa nie ma czego filtrować po wydziale.
    uczelnia.uzywaj_wydzialow = False
    uczelnia.save()

    response = admin_client.get(reverse("admin:bpp_autor_changelist"))
    assert response.status_code == 200
    assert not any(
        isinstance(spec, WydzialAutoraFilter)
        for spec in response.context["cl"].filter_specs
    )


@pytest.mark.django_db
def test_AutorAdmin_WydzialFilter_widoczny_gdy_uczelnia_z_wydzialami(
    admin_client, uczelnia: Uczelnia, jednostka: Jednostka
):
    uczelnia.uzywaj_wydzialow = True
    uczelnia.save()

    response = admin_client.get(reverse("admin:bpp_autor_changelist"))
    assert response.status_code == 200
    assert any(
        isinstance(spec, WydzialAutoraFilter)
        for spec in response.context["cl"].filter_specs
    )


@pytest.mark.django_db
def test_AutorAdmin_stary_querystring_wydzialu_daje_400(
    admin_client, jednostka: Jednostka
):
    # Świadoma zmiana kontraktu URL: filtr zmienił parametr z
    # `?aktualna_jednostka__wydzial__id__exact=<id>` na `?wydzial=<id>`.
    # Filtry admina to ulotny stan UI (a nie trwałe linki), więc zerwanie
    # starych URL-i akceptujemy — ale musi degradować się przewidywalnie,
    # bez 500.
    #
    # ZMIERZONE zachowanie (nie założone): skoro pola nie ma już w
    # `list_filter`, `ChangeList.get_filters` odrzuca lookup jako
    # `DisallowedModelAdminLookup`. To podklasa `SuspiciousOperation`, więc
    # handler wyjątków Django zamienia ją na **400 Bad Request** i loguje w
    # kanale `django.security` — NIE jest to 500 ani redirect na `?e=1`
    # (`?e=1` dostajemy tylko dla `IncorrectLookupParameters`, czyli dla
    # DOZWOLONEGO pola z niepoprawną wartością).
    root = jednostka.parent
    response = admin_client.get(
        reverse("admin:bpp_autor_changelist"),
        {"aktualna_jednostka__wydzial__id__exact": root.pk},
    )
    assert response.status_code == 400
