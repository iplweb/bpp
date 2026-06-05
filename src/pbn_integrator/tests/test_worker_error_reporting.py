"""Regresja: catch-all w wątkach roboczych NIE może połykać błędów po cichu.

Wątki robocze importu/integracji łapią ``except Exception`` i zwracają status
do agregatora (tuple/dict). Wcześniej robiły to BEZ śladu (albo tylko
``logger.info(str(e))`` / ``tqdm.write``), więc błąd „po stronie workera"
ginął — ani Rollbar, ani pełny traceback w logach. Te testy pilnują, że każdy
taki catch-all woła ``logger.exception`` (pełny traceback) ORAZ
``rollbar.report_exc_info``, jednocześnie zachowując dotychczasowy kontrakt
zwracania statusu (nie rzuca).
"""

from unittest.mock import MagicMock, patch


def test_process_journal_thread_safe_reports_on_failure():
    """Błąd importu źródła w wątku → logger.exception + rollbar + status błędu."""
    from pbn_integrator.importer import sources

    pbn_journal = MagicMock()
    pbn_journal.pk = 4242

    with (
        patch.object(sources, "dopisz_jedno_zrodlo", side_effect=ValueError("boom")),
        # close_old_connections dotyka połączenia DB — pacujemy je, żeby test
        # został szybkim unitem bez marka django_db (i nie był wrażliwy na to,
        # czy wcześniejszy test otworzył połączenie).
        patch.object(sources, "close_old_connections"),
        patch.object(sources, "logger") as mock_logger,
        patch.object(sources, "rollbar") as mock_rollbar,
    ):
        result = sources._process_journal_thread_safe(pbn_journal, None, {})

    # Kontrakt zwracania statusu zachowany — NIE rzuca, agregator dostaje błąd.
    assert result["success"] is False
    assert result["journal_id"] == 4242
    assert "boom" in result["error"]

    # Ślad MUSI powstać: pełny traceback w logach + zgłoszenie do Rollbara.
    mock_logger.exception.assert_called_once()
    mock_rollbar.report_exc_info.assert_called_once()


def test_download_and_import_single_publication_reports_on_failure():
    """Błąd importu pojedynczej pracy w wątku → logger.exception + rollbar."""
    from pbn_integrator.utils import publications

    with (
        patch.object(
            publications,
            "_pobierz_pojedyncza_prace",
            side_effect=ValueError("boom"),
        ),
        patch.object(publications, "logger") as mock_logger,
        patch.object(publications, "rollbar") as mock_rollbar,
    ):
        pbn_uid_id, success, error = (
            publications._download_and_import_single_publication(
                client=MagicMock(),
                pbn_uid_id="PBN-UID-1",
                default_jednostka=None,
            )
        )

    assert success is False
    assert pbn_uid_id == "PBN-UID-1"
    assert "boom" in error

    mock_logger.exception.assert_called_once()
    mock_rollbar.report_exc_info.assert_called_once()
