"""Kontekst atrybucji usera dla soft-delete (faza 06, Task 1).

Sygnały pakietu ``django-soft-delete`` niosą wyłącznie ``sender``
i ``instance`` — usera ani powodu nie przekazują. Ten thread-local jest
kanałem, którym ``delete(user=, reason=)`` dostarcza je receiverowi.
"""

import pytest

from bpp.models.soft_delete_context import (
    current_soft_delete_reason,
    current_soft_delete_user,
    soft_delete_context,
)


def test_context_brak_usera_domyslnie():
    assert current_soft_delete_user() is None
    assert current_soft_delete_reason() == ""


def test_context_ustawia_i_czysci(django_user_model, db):
    u = django_user_model.objects.create(username="ktos")
    with soft_delete_context(user=u, reason="literówka"):
        assert current_soft_delete_user() == u
        assert current_soft_delete_reason() == "literówka"
    assert current_soft_delete_user() is None
    assert current_soft_delete_reason() == ""


def test_context_zagniezdzony_przywraca_zewnetrzny(django_user_model, db):
    """Reentrancja: kaskada ``*_Autor`` odpala się WEWNĄTRZ kontekstu
    rodzica, więc zagnieżdżone wejście nie może zgubić usera zewnętrznego.
    """
    a = django_user_model.objects.create(username="a")
    b = django_user_model.objects.create(username="b")
    with soft_delete_context(user=a, reason="zewn"):
        with soft_delete_context(user=b, reason="wewn"):
            assert current_soft_delete_user() == b
            assert current_soft_delete_reason() == "wewn"
        assert current_soft_delete_user() == a
        assert current_soft_delete_reason() == "zewn"
    assert current_soft_delete_user() is None


def test_context_czysci_takze_przy_wyjatku(django_user_model, db):
    """``delete()`` może paść (np. ``ProtectedError`` guardu fazy 04).

    Gdyby kontekst przeciekł, NASTĘPNA operacja w tym samym wątku —
    w produkcji: kolejny request na tym samym workerze gunicorna —
    zalogowałaby cudzego usera. To cichy błąd atrybucji audytu, więc
    sprzątanie musi być w ``finally``, nie po ``yield``.
    """
    u = django_user_model.objects.create(username="pechowiec")
    with pytest.raises(ValueError):
        with soft_delete_context(user=u, reason="bum"):
            raise ValueError("bum")
    assert current_soft_delete_user() is None
    assert current_soft_delete_reason() == ""
