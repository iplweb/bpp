from unittest.mock import patch

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


@pytest.mark.django_db
def test_oblicz_metryki_dla_autora_task():
    """Test pojedynczego taska obliczającego metryki dla autora"""
    from ewaluacja_metryki.tasks import oblicz_metryki_dla_autora_task

    # Patchuj w źródłowym module
    with patch(
        "ewaluacja_liczba_n.models.IloscUdzialowDlaAutoraZaCalosc"
    ) as mock_model:
        # Mock queryset
        mock_queryset = mock_model.objects.select_related.return_value
        mock_instance = mock_queryset.get.return_value

        # Ustaw wartości na mocku
        mock_instance.autor = "Jan Kowalski"
        mock_instance.dyscyplina_naukowa.nazwa = "Matematyka"

        # Mock _process_single_author z utils.py
        with patch("ewaluacja_metryki.utils._process_single_author") as mock_process:
            mock_process.return_value = ("processed", "Test message")

            # Wywołaj task
            result = oblicz_metryki_dla_autora_task(
                ilosc_udzialow_id=123,
                rok_min=2022,
                rok_max=2025,
                minimalny_pk=0.01,
                rodzaje_autora=["N"],
            )

            # Sprawdź wynik
            assert result["status"] == "processed"
            assert "autor" in result
            assert "dyscyplina" in result
            assert "message" in result

            # Sprawdź że _process_single_author został wywołany
            mock_process.assert_called_once()


@pytest.mark.django_db
def test_oblicz_metryki_dla_autora_task_nieistniejacy_id():
    """Test taska z nieistniejącym ID"""
    from ewaluacja_metryki.tasks import oblicz_metryki_dla_autora_task

    # Wywołaj task z nieistniejącym ID
    result = oblicz_metryki_dla_autora_task(
        ilosc_udzialow_id=999999,
        rok_min=2022,
        rok_max=2025,
        minimalny_pk=0.01,
        rodzaje_autora=["N"],
    )

    # Sprawdź że zwrócił błąd
    assert result["status"] == "error"
    assert "nie istnieje" in result["message"]


@pytest.mark.django_db
def test_finalizuj_generowanie_metryk():
    """Test callback taska finalizującego generowanie"""
    from django.db.models import F

    from ewaluacja_metryki.models import StatusGenerowania
    from ewaluacja_metryki.tasks import finalizuj_generowanie_metryk

    # Przygotuj status generowania
    status = StatusGenerowania.get_or_create()
    status.rozpocznij_generowanie(task_id="test-task-id", liczba_do_przetworzenia=5)

    # Przygotuj wyniki z tasków
    results = [
        {
            "status": "processed",
            "autor": "Jan Kowalski",
            "dyscyplina": "Matematyka",
            "message": "OK",
        },
        {
            "status": "processed",
            "autor": "Anna Nowak",
            "dyscyplina": "Fizyka",
            "message": "OK",
        },
        {
            "status": "skipped",
            "autor": "Piotr Wiśniewski",
            "dyscyplina": "Chemia",
            "message": "Pominięto",
        },
        {
            "status": "error",
            "autor": "Maria Dąbrowska",
            "dyscyplina": "Biologia",
            "message": "Błąd",
        },
        {
            "status": "processed",
            "autor": "Tomasz Lewandowski",
            "dyscyplina": "Informatyka",
            "message": "OK",
        },
    ]

    # Symuluj atomowe update'y licznika przez poszczególne taski
    # (w prawdziwym scenariuszu każdy task wywołuje StatusGenerowania.objects.update(...))
    for result in results:
        StatusGenerowania.objects.update(
            liczba_przetworzonych=F("liczba_przetworzonych") + 1
        )

    # Wywołaj callback
    result = finalizuj_generowanie_metryk(results)

    # Sprawdź wynik - teraz używa liczba_przetworzonych z bazy (5 - wszystkie taski się zakończyły)
    assert result["success"] is True
    assert result["processed"] == 5  # Wszystkie taski zwiększyły licznik
    assert result["skipped"] == 1
    assert result["errors"] == 1
    assert result["total"] == 5

    # Sprawdź że status został zaktualizowany
    status.refresh_from_db()
    assert status.w_trakcie is False
    assert status.data_zakonczenia is not None
    assert status.liczba_przetworzonych == 5  # Atomowo zaktualizowana przez 5 tasków
    assert status.liczba_bledow == 1


@pytest.mark.django_db
def test_oblicz_metryki_dla_autora_task_inkrementuje_licznik():
    """Test że task atomowo inkrementuje licznik w StatusGenerowania"""
    from ewaluacja_metryki.models import StatusGenerowania
    from ewaluacja_metryki.tasks import oblicz_metryki_dla_autora_task

    # Przygotuj status generowania
    status = StatusGenerowania.get_or_create()
    status.rozpocznij_generowanie(task_id="test-task", liczba_do_przetworzenia=5)
    assert status.liczba_przetworzonych == 0

    # Patchuj w źródłowym module
    with patch(
        "ewaluacja_liczba_n.models.IloscUdzialowDlaAutoraZaCalosc"
    ) as mock_model:
        # Mock queryset
        mock_queryset = mock_model.objects.select_related.return_value
        mock_instance = mock_queryset.get.return_value

        # Ustaw wartości na mocku
        mock_instance.autor = "Jan Kowalski"
        mock_instance.dyscyplina_naukowa.nazwa = "Matematyka"

        # Mock _process_single_author z utils.py
        with patch("ewaluacja_metryki.utils._process_single_author") as mock_process:
            mock_process.return_value = ("processed", "Test message")

            # Wywołaj task pierwszy raz
            oblicz_metryki_dla_autora_task(
                ilosc_udzialow_id=123,
                rok_min=2022,
                rok_max=2025,
                minimalny_pk=0.01,
                rodzaje_autora=["N"],
            )

            # Sprawdź że licznik wzrósł o 1
            status.refresh_from_db()
            assert status.liczba_przetworzonych == 1

            # Wywołaj task drugi raz
            oblicz_metryki_dla_autora_task(
                ilosc_udzialow_id=124,
                rok_min=2022,
                rok_max=2025,
                minimalny_pk=0.01,
                rodzaje_autora=["N"],
            )

            # Sprawdź że licznik wzrósł o kolejne 1
            status.refresh_from_db()
            assert status.liczba_przetworzonych == 2


@pytest.mark.django_db
def test_generuj_metryki_task_parallel_uruchamia_chord():
    """Test że równoległy task tworzy chord z taskami"""
    from unittest.mock import MagicMock

    from ewaluacja_metryki.tasks import generuj_metryki_task_parallel

    # Mock oblicz_liczby_n żeby nie wykonywać prawdziwych obliczeń
    with patch("ewaluacja_metryki.tasks.oblicz_liczby_n_dla_ewaluacji_2022_2025"):
        # Mock IloscUdzialowDlaAutoraZaCalosc - patchuj w źródłowym module
        with patch(
            "ewaluacja_liczba_n.models.IloscUdzialowDlaAutoraZaCalosc"
        ) as mock_ilosc:
            # Mock queryset chain: all() -> filter() -> values_list()
            mock_queryset = MagicMock()
            mock_queryset.filter.return_value = mock_queryset
            mock_queryset.values_list.return_value = [1, 2, 3]
            mock_ilosc.objects.all.return_value = mock_queryset

            # Mock MetrykaAutora
            with patch(
                "ewaluacja_metryki.tasks.MetrykaAutora", create=True
            ) as mock_metryka:
                mock_metryka.objects.all.return_value.count.return_value = 0
                mock_metryka.objects.all.return_value.delete.return_value = None

                # Mock StatusGenerowania żeby nie zapisywał do bazy
                with patch(
                    "ewaluacja_metryki.tasks.StatusGenerowania"
                ) as mock_status_class:
                    mock_status = MagicMock()
                    mock_status_class.get_or_create.return_value = mock_status

                    # Mock chord żeby nie uruchamiać prawdziwych tasków
                    with patch("ewaluacja_metryki.tasks.chord") as mock_chord:
                        # Mock group
                        with patch("ewaluacja_metryki.tasks.group") as mock_group:
                            # Mock zwrotnej wartości chord - utwórz mock z parent
                            mock_chord_result = mock_chord.return_value.return_value
                            mock_chord_result.id = "test-chord-id"
                            mock_chord_result.parent = MagicMock()
                            mock_chord_result.parent.id = "test-group-id"

                            # Wywołaj task
                            result = generuj_metryki_task_parallel(
                                rok_min=2022,
                                rok_max=2025,
                                minimalny_pk=0.01,
                                nadpisz=True,
                                przelicz_liczbe_n=True,
                            )

                            # Sprawdź że chord został utworzony
                            mock_group.assert_called_once()
                            mock_chord.assert_called_once()

                            # Sprawdź że StatusGenerowania.rozpocznij_generowanie() został wywołany
                            mock_status.rozpocznij_generowanie.assert_called_once()

                            # Sprawdź wynik
                            assert result["success"] is True
                            assert result["total"] == 3
                            assert "task_id" in result
                            assert result["group_id"] == "test-group-id"
