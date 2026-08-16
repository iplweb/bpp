"""Praca w koszu nie liczy się do ewaluacji (faza 06, Task 6b).

Luka nieobjęta żadnym innym mechanizmem: ``Cache_Punktacja_Autora``
i ``Cache_Punktacja_Dyscypliny`` NIE MAJĄ FK do publikacji — kluczem jest
tablica ``rekord_id = [content_type_id, pk]``. Nie rusza ich więc ani
kaskada Django, ani wąska kaskada ``*_Autor`` z fazy 02, ani triggery
denormalizacji. Bez receiverów soft-deletowana praca nadal wnosiłaby sloty
i punkty do ewaluacji.
"""

import pytest
from django.contrib.contenttypes.models import ContentType

from bpp.models.cache.punktacja import (
    Cache_Punktacja_Autora,
    Cache_Punktacja_Dyscypliny,
)


def _klucz(rekord):
    # ``content_type`` nie jest atrybutem modeli publikacji (to property na
    # RekordBase), więc bierzemy przez ContentType.
    return [ContentType.objects.get_for_model(type(rekord)).pk, rekord.pk]


@pytest.mark.django_db
def test_soft_delete_kasuje_cache_punktacji(zwarte_z_dyscyplinami, bez_celery):
    zw = zwarte_z_dyscyplinami
    zw.przelicz_punkty_dyscyplin()
    klucz = _klucz(zw)

    assert Cache_Punktacja_Autora.objects.filter(rekord_id=klucz).exists()
    assert Cache_Punktacja_Dyscypliny.objects.filter(rekord_id=klucz).exists()

    zw.delete()

    assert not Cache_Punktacja_Autora.objects.filter(rekord_id=klucz).exists()
    assert not Cache_Punktacja_Dyscypliny.objects.filter(rekord_id=klucz).exists()


@pytest.mark.django_db
def test_restore_przywraca_cache_punktacji(zwarte_z_dyscyplinami, bez_celery):
    zw = zwarte_z_dyscyplinami
    zw.przelicz_punkty_dyscyplin()
    klucz = _klucz(zw)

    zw.delete()
    assert not Cache_Punktacja_Autora.objects.filter(rekord_id=klucz).exists()

    zw.restore()

    assert Cache_Punktacja_Autora.objects.filter(rekord_id=klucz).exists()
    assert Cache_Punktacja_Dyscypliny.objects.filter(rekord_id=klucz).exists()


@pytest.mark.django_db
def test_przeliczenie_zachodzi_raz_mimo_kaskady(zwarte_z_dyscyplinami, bez_celery):
    """Kaskada ``*_Autor`` NIE MOŻE wyzwalać przeliczenia po raz drugi.

    Soft-delete publikacji z N autorami emituje 1 + N sygnałów. Gdyby
    kasowanie punktacji zachodziło przy każdym, dokładalibyśmy N-1 zbędnych
    par zapytań do każdego usunięcia. Gate po ``ModelZPrzeliczaniemDyscyplin``
    zawęża to do sygnału rodzica — wiersze ``*_Autor`` tego abstraktu nie
    dziedziczą.
    """
    from unittest.mock import patch

    zw = zwarte_z_dyscyplinami
    zw.przelicz_punkty_dyscyplin()
    assert zw.autorzy_set.count() >= 2, "test ma sens tylko dla >1 autorstwa"

    with patch("bpp.models.sloty.core.IPunktacjaCacher.removeEntries") as mock_remove:
        zw.delete()

    assert mock_remove.call_count == 1


@pytest.mark.django_db
def test_autor_nie_dotyka_cache_punktacji(autor_jan_kowalski, bez_celery):
    """Receiver jest globalny — dla ``Autor`` ta gałąź nie może się odpalić.

    ``Autor`` nie ma ``przelicz_punkty_dyscyplin()``; bez gate'u receiver
    wywaliłby się na ``AttributeError`` przy każdym soft-delete autora.
    """
    from unittest.mock import patch

    with patch("bpp.models.sloty.core.IPunktacjaCacher") as mock_cacher:
        autor_jan_kowalski.delete()

    mock_cacher.assert_not_called()
