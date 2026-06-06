"""Focused tests for publication import step behavior."""

from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from bpp.models import (
    Dyscyplina_Naukowa,
    Jednostka,
    Rodzaj_Zrodla,
    Uczelnia,
)
from pbn_api.models import Institution, Publication
from pbn_import.models import ImportSession
from pbn_import.utils.base import CancelledException
from pbn_import.utils.publication_import import PublicationImporter


@pytest.fixture
def session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make(ImportSession, user=user, config={})


@pytest.fixture
def uczelnia(db):
    return baker.make(Uczelnia, pbn_uid=baker.make(Institution))


@pytest.fixture
def importer(session, uczelnia):
    imp = PublicationImporter(session, client=MagicMock(), uczelnia=uczelnia)
    imp.default_jednostka = baker.make(Jednostka, nazwa="Default unit", uczelnia=uczelnia)
    return imp


def test_setup_wires_default_jezyk_from_resolver(importer):
    """``_setup_uczelnia_and_jednostka`` ustawia ``self.default_jezyk``.

    Bez wyboru w configu resolver zwraca polski — i to on (a nie None) jedzie
    potem do importera jako ``domyslny_jezyk``.
    """
    from bpp.models import Jezyk

    importer._setup_uczelnia_and_jednostka()

    assert importer.default_jezyk == Jezyk.objects.get(skrot="pol.")


def test_run_returns_reason_when_uczelnia_setup_is_missing(session):
    importer = PublicationImporter(session, client=MagicMock(), uczelnia=None)

    with patch.object(importer, "_setup_uczelnia_and_jednostka", return_value=None):
        result = importer.run()

    assert result == {"authors_imported": False, "reason": "No Uczelnia PBN UID"}


def test_run_success_with_delete_existing_calls_steps_in_order(importer, uczelnia):
    importer.delete_existing = True

    with patch.object(
        importer, "_setup_uczelnia_and_jednostka", return_value=uczelnia
    ) as setup:
        with patch.object(
            importer, "_delete_existing_publications", return_value=None
        ) as delete_existing:
            with patch.object(
                importer, "_download_publications", return_value=None
            ) as download:
                with patch.object(
                    importer, "_download_publications_v2", return_value=None
                ) as download_v2:
                    with patch.object(
                        importer, "_import_publications", return_value=None
                    ) as import_publications:
                        with patch.object(importer, "update_progress") as progress:
                            result = importer.run()

    setup.assert_called_once_with()
    delete_existing.assert_called_once_with(0, 4)
    download.assert_called_once_with(1, 4, uczelnia)
    download_v2.assert_called_once_with(2, 4)
    import_publications.assert_called_once_with(3, 4)
    progress.assert_called_once_with(4, 4, "Zakończono import publikacji")
    assert result == {
        "publications_imported": True,
        "default_jednostka": "Default unit",
        "error_count": 0,
    }


def test_run_short_circuits_when_delete_existing_returns_result(importer, uczelnia):
    importer.delete_existing = True

    with patch.object(importer, "_setup_uczelnia_and_jednostka", return_value=uczelnia):
        with patch.object(
            importer, "_delete_existing_publications", return_value={"cancelled": True}
        ):
            with patch.object(importer, "_download_publications") as download:
                result = importer.run()

    assert result == {"cancelled": True}
    download.assert_not_called()


def test_delete_existing_returns_cancelled_before_deleting(importer):
    with patch.object(importer, "check_cancelled", return_value=True):
        with patch("pbn_import.utils.publication_import.Wydawnictwo_Zwarte") as zwarte:
            result = importer._delete_existing_publications(0, 3)

    assert result == {"cancelled": True}
    zwarte.objects.exclude.assert_not_called()


def test_download_publications_success_uses_progress_callback(importer, uczelnia):
    callback = MagicMock()

    with patch.object(importer, "check_cancelled", return_value=False):
        with patch.object(importer, "create_subtask_progress", return_value=callback):
            with patch(
                "pbn_import.utils.publication_import.pobierz_publikacje_z_instytucji"
            ) as download:
                result = importer._download_publications(1, 3, uczelnia)

    assert result is None
    download.assert_called_once_with(importer.client, callback=callback)


def test_download_publications_delegates_pbn_error(importer, uczelnia):
    error = RuntimeError("pbn unavailable")

    with patch.object(importer, "check_cancelled", return_value=False):
        with patch(
            "pbn_import.utils.publication_import.pobierz_publikacje_z_instytucji",
            side_effect=error,
        ):
            with patch.object(importer, "handle_pbn_error") as handle_pbn_error:
                importer._download_publications(1, 3, uczelnia)

    handle_pbn_error.assert_called_once_with(
        error, "Nie udało się pobrać publikacji"
    )


def test_download_publications_v2_clears_progress_even_on_error(importer):
    error = RuntimeError("v2 failed")

    with patch.object(importer, "check_cancelled", return_value=False):
        with patch.object(importer, "create_subtask_progress", return_value=MagicMock()):
            with patch.object(
                importer, "_download_publications_v2_with_callback", side_effect=error
            ):
                with patch.object(importer, "handle_pbn_error") as handle_pbn_error:
                    with patch.object(importer, "clear_subtask_progress") as clear:
                        importer._download_publications_v2(2, 3)

    handle_pbn_error.assert_called_once_with(
        error, "Nie udało się pobrać publikacji v2"
    )
    assert clear.call_count == 2


def test_import_publications_success_calls_import_helper(importer):
    with patch.object(importer, "check_cancelled", return_value=False):
        with patch.object(importer, "_import_publications_with_cancellation") as helper:
            result = importer._import_publications(2, 3)

    assert result is None
    helper.assert_called_once_with()


def test_import_publications_logs_helper_error_and_continues(importer):
    error = RuntimeError("broken publication")

    with patch.object(importer, "check_cancelled", return_value=False):
        with patch.object(
            importer, "_import_publications_with_cancellation", side_effect=error
        ):
            with patch.object(importer, "handle_error") as handle_error:
                result = importer._import_publications(2, 3)

    assert result is None
    handle_error.assert_called_once_with(error, "Nie udało się zaimportować publikacji")


def test_import_publications_with_cancellation_imports_and_records_failures(importer):
    rodzaj_periodyk, _ = Rodzaj_Zrodla.objects.get_or_create(nazwa="periodyk")
    dyscyplina, _ = Dyscyplina_Naukowa.objects.get_or_create(
        kod="2.3", defaults={"nazwa": "Informatyka"}
    )
    pub_ok = baker.make(Publication, mongoId="pub-ok")
    pub_bad = baker.make(Publication, mongoId="pub-bad")

    def passthrough_pbar(iterator, count, label, callback):
        return iterator

    def fake_import_one(pbn_uid, **kwargs):
        if pbn_uid == pub_bad.mongoId:
            raise RuntimeError("bad import")
        return True

    with patch("bpp.util.pbar", side_effect=passthrough_pbar):
        with patch.object(importer, "check_cancelled", return_value=False):
            with patch.object(importer, "create_subtask_progress", return_value=MagicMock()):
                with patch.object(importer, "handle_error") as handle_error:
                    with patch(
                        "pbn_import.utils.publication_import."
                        "importuj_publikacje_po_pbn_uid_id",
                        side_effect=fake_import_one,
                    ) as import_one:
                        importer._import_publications_with_cancellation()

    assert {args.args[0] for args in import_one.call_args_list} == {
        pub_ok.mongoId,
        pub_bad.mongoId,
    }
    for import_call in import_one.call_args_list:
        assert import_call.kwargs == {
            "client": importer.client,
            "default_jednostka": importer.default_jednostka,
            "rodzaj_periodyk": rodzaj_periodyk,
            "dyscypliny_cache": {dyscyplina.nazwa: dyscyplina},
            "domyslny_jezyk": importer.default_jezyk,
        }
    handle_error.assert_called_once()
    assert "pub-bad" in handle_error.call_args.args[1]


def test_import_publications_with_cancellation_raises_when_session_cancelled(importer):
    Rodzaj_Zrodla.objects.get_or_create(nazwa="periodyk")
    baker.make(Publication, mongoId="pub-cancelled")

    def passthrough_pbar(iterator, count, label, callback):
        return iterator

    with patch("bpp.util.pbar", side_effect=passthrough_pbar):
        with patch.object(importer, "check_cancelled", return_value=True):
            with pytest.raises(CancelledException, match="Import został anulowany"):
                importer._import_publications_with_cancellation()
