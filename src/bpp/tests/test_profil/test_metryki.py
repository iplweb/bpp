"""Sekcja „Metryki ewaluacyjne” na podstronie autora — widoczność przycisku.

Przycisk prowadzi do ``MetrykaDetailView``, który wpuszcza tylko pełne
uprawnienia ewaluacji albo zalogowanego autora oglądającego własne metryki.
Pozostałym (anonim, zwykły użytkownik, inny autor) sekcji nie pokazujemy.
"""

from decimal import Decimal

import pytest

from ewaluacja_metryki.models import MetrykaAutora

NAGLOWEK = "Metryki ewaluacyjne"


@pytest.fixture
def metryka(autor_jan_kowalski, dyscyplina1, uczelnia):
    return MetrykaAutora.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        uczelnia=uczelnia,
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("2.0"),
        punkty_nazbierane=Decimal("100.0"),
        slot_wszystkie=Decimal("3.0"),
        punkty_wszystkie=Decimal("150.0"),
    )


def _tresc(client, autor):
    return client.get(autor.get_absolute_url()).content.decode()


@pytest.mark.django_db
def test_metryki_ukryte_dla_anonima(client, metryka):
    assert NAGLOWEK not in _tresc(client, metryka.autor)


@pytest.mark.django_db
def test_metryki_ukryte_dla_zwyklego_uzytkownika(client, metryka, normal_django_user):
    client.force_login(normal_django_user)
    assert NAGLOWEK not in _tresc(client, metryka.autor)


@pytest.mark.django_db
def test_metryki_ukryte_dla_innego_autora(
    client, metryka, normal_django_user, autor_jan_nowak
):
    normal_django_user.autor = autor_jan_nowak
    normal_django_user.save()
    client.force_login(normal_django_user)
    assert NAGLOWEK not in _tresc(client, metryka.autor)


@pytest.mark.django_db
def test_metryki_widoczne_dla_autora_na_wlasnej_stronie(
    client, metryka, normal_django_user
):
    normal_django_user.autor = metryka.autor
    normal_django_user.save()
    client.force_login(normal_django_user)
    tresc = _tresc(client, metryka.autor)
    assert NAGLOWEK in tresc
    assert metryka.get_absolute_url() in tresc


@pytest.mark.django_db
def test_metryki_widoczne_dla_wprowadzania_danych(
    client, metryka, wprowadzanie_danych_user
):
    client.force_login(wprowadzanie_danych_user)
    assert NAGLOWEK in _tresc(client, metryka.autor)


@pytest.mark.django_db
def test_metryki_widoczne_dla_superusera(client, metryka, admin_user):
    client.force_login(admin_user)
    assert NAGLOWEK in _tresc(client, metryka.autor)
