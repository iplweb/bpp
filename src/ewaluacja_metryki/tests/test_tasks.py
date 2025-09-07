from unittest.mock import MagicMock, patch

import pytest

from ewaluacja_metryki.models import StatusGenerowania
from ewaluacja_metryki.tasks import generuj_metryki_task


@pytest.mark.django_db
def test_generuj_metryki_task_success():
    """Test pomyślnego wykonania taska generowania metryk"""

    # Mockuj call_command
    with patch("ewaluacja_metryki.tasks.call_command") as mock_call_command:
        # Symuluj output z management command
        mock_call_command.return_value = None

        # Mockuj self.request.id
        task = generuj_metryki_task
        task.request = MagicMock()
        task.request.id = "test-task-123"

        # Ustaw fake output dla parsowania
        with patch("io.StringIO") as mock_string_io:
            mock_output = MagicMock()
            mock_output.getvalue.return_value = (
                "Zakończono: przetworzono 5, pominięto 0, błędy 1"
            )
            mock_string_io.return_value = mock_output

            result = generuj_metryki_task(
                rok_min=2022, rok_max=2025, minimalny_pk=0.01, nadpisz=True
            )

    assert result["success"] is True
    assert "Wygenerowano metryki" in result["message"]

    # Sprawdź status
    status = StatusGenerowania.get_or_create()
    assert status.w_trakcie is False
    assert status.data_zakonczenia is not None


@pytest.mark.django_db
def test_generuj_metryki_task_already_running():
    """Test gdy generowanie jest już w trakcie"""

    # Ustaw status jako w trakcie
    status = StatusGenerowania.get_or_create()
    status.rozpocznij_generowanie(task_id="other-task")

    # Mockuj self.request.id
    task = generuj_metryki_task
    task.request = MagicMock()
    task.request.id = "test-task-456"

    result = generuj_metryki_task()

    assert result["success"] is False
    assert "już w trakcie" in result["message"]
    assert result["task_id"] == "other-task"


@pytest.mark.django_db
def test_generuj_metryki_task_error():
    """Test obsługi błędu podczas generowania"""

    # Mockuj call_command aby rzucił wyjątek
    with patch("ewaluacja_metryki.tasks.call_command") as mock_call_command:
        mock_call_command.side_effect = Exception("Test error")

        # Mockuj self.request.id
        task = generuj_metryki_task
        task.request = MagicMock()
        task.request.id = "test-task-789"

        result = generuj_metryki_task()

    assert result["success"] is False
    assert "Test error" in result["message"]

    # Sprawdź status
    status = StatusGenerowania.get_or_create()
    assert status.w_trakcie is False
    assert "Błąd: Test error" in status.ostatni_komunikat


@pytest.mark.django_db
def test_generuj_metryki_task_parsowanie_outputu():
    """Test parsowania outputu z management command"""

    with patch("ewaluacja_metryki.tasks.call_command") as mock_call_command:
        mock_call_command.return_value = None

        # Mockuj self.request.id
        task = generuj_metryki_task
        task.request = MagicMock()
        task.request.id = "test-parse"

        # Symuluj różne outputy
        test_cases = [
            ("Zakończono: przetworzono 15, pominięto 3, błędy 2", 15, 2),
            ("Coś innego\nZakończono: przetworzono 8, pominięto 0, błędy 0", 8, 0),
            ("Brak linii zakończenia", 0, 0),
        ]

        for output_text, expected_processed, expected_errors in test_cases:
            with patch("io.StringIO") as mock_string_io:
                mock_output = MagicMock()
                mock_output.getvalue.return_value = output_text
                mock_string_io.return_value = mock_output

                result = generuj_metryki_task()

                assert result["przetworzonych"] == expected_processed
                assert result["bledow"] == expected_errors
