import pytest


@pytest.mark.django_db
def test_generowanie_wywoluje_obliczanie_liczby_n():
    """Test sprawdzający, że moduł ewaluacja_metryki korzysta z funkcji obliczania liczby N"""
    # Ten test sprawdza integrację między modułami

    # 1. Sprawdź import w tasks.py
    from ewaluacja_metryki import tasks

    assert hasattr(tasks, "oblicz_liczby_n_dla_ewaluacji_2022_2025")

    # 2. Sprawdź import w management command
    from ewaluacja_metryki.management.commands import oblicz_metryki

    assert hasattr(oblicz_metryki, "oblicz_liczby_n_dla_ewaluacji_2022_2025")

    # 3. Sprawdź, że funkcja jest używana w kodzie tasks.py
    import inspect

    source = inspect.getsource(tasks.generuj_metryki_task)
    assert "oblicz_liczby_n_dla_ewaluacji_2022_2025" in source
    assert "przelicz_liczbe_n" in source

    # 4. Sprawdź, że management command używa funkcji
    source_cmd = inspect.getsource(oblicz_metryki.Command.handle)
    assert "oblicz_liczby_n_dla_ewaluacji_2022_2025" in source_cmd
    assert "bez_liczby_n" in source_cmd
