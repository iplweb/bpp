"""Focused tests for small PBN import step wrappers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia
from pbn_api.models import Institution
from pbn_import.models import ImportInconsistency, ImportLog, ImportSession
from pbn_import.utils.author_import import AuthorImporter
from pbn_import.utils.conference_import import ConferenceImporter
from pbn_import.utils.fee_import import FeeImporter
from pbn_import.utils.publisher_import import PublisherImporter
from pbn_import.utils.source_import import SourceImporter
from pbn_import.utils.statement_import import StatementImporter


@pytest.fixture
def session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make(ImportSession, user=user, config={})


@pytest.fixture
def uczelnia(db):
    return baker.make(Uczelnia, pbn_uid=baker.make(Institution))


def test_author_importer_skips_without_uczelnia_uid(session):
    result = AuthorImporter(session, client=MagicMock(), uczelnia=None).run()

    assert result == {"authors_imported": False, "reason": "No Uczelnia PBN UID"}
    assert ImportLog.objects.filter(session=session, level="warning").exists()


def test_author_importer_downloads_and_integrates_authors(session, uczelnia):
    importer = AuthorImporter(session, client=MagicMock(), uczelnia=uczelnia)
    callback = MagicMock()

    with patch.object(importer, "create_subtask_progress", return_value=callback):
        with patch.object(importer, "clear_subtask_progress") as clear:
            with patch("pbn_import.utils.author_import.pobierz_ludzi_z_uczelni") as dl:
                with patch(
                    "pbn_import.utils.author_import.integruj_autorow_z_uczelni"
                ) as integrate:
                    result = importer.run()

    dl.assert_called_once_with(importer.client, uczelnia.pbn_uid_id, callback=callback)
    integrate.assert_called_once_with(
        importer.client,
        uczelnia.pbn_uid_id,
        import_unexistent=True,
        callback=callback,
    )
    assert clear.call_count == 2
    assert result == {
        "authors_imported": True,
        "uczelnia_pbn_uid": uczelnia.pbn_uid_id,
        "error_count": 0,
    }


def test_author_importer_records_download_and_integration_errors(session, uczelnia):
    importer = AuthorImporter(session, client=MagicMock(), uczelnia=uczelnia)

    with patch.object(importer, "create_subtask_progress", return_value=MagicMock()):
        with patch(
            "pbn_import.utils.author_import.pobierz_ludzi_z_uczelni",
            side_effect=RuntimeError("download failed"),
        ):
            with patch(
                "pbn_import.utils.author_import.integruj_autorow_z_uczelni",
                side_effect=RuntimeError("integration failed"),
            ):
                with patch(
                    "pbn_import.utils.base.rollbar.report_exc_info"
                ) as report_exc_info:
                    result = importer.run()

    assert report_exc_info.call_count == 2
    assert result["error_count"] == 2
    assert importer.errors == [
        "Nie udało się pobrać autorów: download failed",
        "Nie udało się zintegrować autorów: integration failed",
    ]
    assert (
        list(
            ImportLog.objects.filter(session=session, level="error")
            .order_by("pk")
            .values_list("message", flat=True)
        )
        == importer.errors
    )


def test_source_importer_success(session):
    importer = SourceImporter(session, client=MagicMock())
    callback = MagicMock()

    with patch.object(importer, "create_subtask_progress", return_value=callback):
        with patch("pbn_import.utils.source_import.pobierz_zrodla_mnisw") as download:
            with patch(
                "pbn_import.utils.source_import.importer.importuj_zrodla",
                return_value=12,
            ) as import_sources:
                result = importer.run()

    download.assert_called_once_with(importer.client, callback=callback)
    import_sources.assert_called_once_with()
    assert result == {"sources_imported": True, "error_count": 0}


def test_source_importer_reraises_database_import_error(session):
    importer = SourceImporter(session, client=MagicMock())

    with patch.object(importer, "create_subtask_progress", return_value=MagicMock()):
        with patch("pbn_import.utils.source_import.pobierz_zrodla_mnisw"):
            with patch(
                "pbn_import.utils.source_import.importer.importuj_zrodla",
                side_effect=RuntimeError("import failed"),
            ):
                with patch.object(importer, "handle_error") as handle_error:
                    with pytest.raises(RuntimeError, match="import failed"):
                        importer.run()

    handle_error.assert_called_once()


def test_source_importer_continues_after_non_auth_download_error(session):
    importer = SourceImporter(session, client=MagicMock())

    with patch.object(importer, "create_subtask_progress", return_value=MagicMock()):
        with patch(
            "pbn_import.utils.source_import.pobierz_zrodla_mnisw",
            side_effect=RuntimeError("download failed"),
        ):
            with patch.object(importer, "handle_pbn_error") as handle_pbn_error:
                with patch("pbn_import.utils.source_import.importer.importuj_zrodla"):
                    result = importer.run()

    handle_pbn_error.assert_called_once()
    assert result["sources_imported"] is True


def test_publisher_importer_success_and_clears_progress(session):
    importer = PublisherImporter(session, client=MagicMock())
    callback = MagicMock()

    with patch.object(importer, "create_subtask_progress", return_value=callback):
        with patch.object(importer, "clear_subtask_progress") as clear:
            with patch(
                "pbn_import.utils.publisher_import.pobierz_wydawcow_mnisw"
            ) as dl:
                with patch(
                    "pbn_import.utils.publisher_import.importer.importuj_wydawcow",
                    return_value=5,
                ) as import_publishers:
                    result = importer.run()

    dl.assert_called_once_with(importer.client)
    import_publishers.assert_called_once_with(callback=callback)
    clear.assert_called_once_with()
    assert result == {"publishers_imported": True, "error_count": 0}


def test_publisher_importer_records_both_download_and_import_errors(session):
    importer = PublisherImporter(session, client=MagicMock())

    with patch.object(importer, "create_subtask_progress", return_value=MagicMock()):
        with patch(
            "pbn_import.utils.publisher_import.pobierz_wydawcow_mnisw",
            side_effect=RuntimeError("download failed"),
        ):
            with patch(
                "pbn_import.utils.publisher_import.importer.importuj_wydawcow",
                side_effect=RuntimeError("import failed"),
            ):
                with patch.object(importer, "handle_error") as handle_error:
                    result = importer.run()

    assert handle_error.call_count == 2
    assert result["publishers_imported"] is True


def test_conference_importer_success_and_error_paths(session):
    importer = ConferenceImporter(session, client=MagicMock())

    with patch.object(importer, "create_subtask_progress", return_value=MagicMock()):
        with patch("pbn_import.utils.conference_import.pobierz_konferencje") as dl:
            with patch(
                "pbn_import.utils.conference_import.integruj_konferencje",
                return_value=0,
            ) as integrate:
                result = importer.run()

    dl.assert_called_once()
    integrate.assert_called_once()
    assert result == {"conferences_imported": True, "error_count": 0}

    failing = ConferenceImporter(session, client=MagicMock())
    with patch.object(failing, "create_subtask_progress", return_value=MagicMock()):
        with patch(
            "pbn_import.utils.conference_import.pobierz_konferencje",
            side_effect=RuntimeError("conference failed"),
        ):
            with patch(
                "pbn_import.utils.conference_import.integruj_konferencje",
                return_value=0,
            ):
                with patch.object(failing, "handle_error") as handle_error:
                    result = failing.run()

    handle_error.assert_called_once()
    assert result["conferences_imported"] is True


class FakeRecord:
    def __init__(self, pbn_uid_id):
        self.pbn_uid_id = pbn_uid_id
        self.save = MagicMock()


class FakePublicationClass:
    def __init__(self, name, records):
        self.__name__ = name
        self.objects = MagicMock()
        self.objects.exclude.return_value = records


def test_fee_importer_updates_records_from_batch_api(session):
    record = FakeRecord(123)
    ciagle = FakePublicationClass("Wydawnictwo_Ciagle", [record])
    zwarte = FakePublicationClass("Wydawnictwo_Zwarte", [])
    client = MagicMock()
    client.get_publication_fees_batch.return_value = {
        "123": {
            "fee": {
                "costFreePublication": True,
                "researchPotentialFinancialResources": True,
                "researchOrDevelopmentProjectsFinancialResources": False,
                "other": True,
                "amount": 250,
            }
        }
    }

    with patch("pbn_import.utils.fee_import.Wydawnictwo_Ciagle", ciagle):
        with patch("pbn_import.utils.fee_import.Wydawnictwo_Zwarte", zwarte):
            result = FeeImporter(session, client=client).run()

    client.get_publication_fees_batch.assert_called_once_with([123])
    assert record.opl_pub_cost_free is True
    assert record.opl_pub_research_potential is True
    assert record.opl_pub_research_or_development_projects is False
    assert record.opl_pub_other is True
    assert record.opl_pub_amount == 250
    record.save.assert_called_once()
    assert result == {
        "fees_imported": 1,
        "fees_failed": 0,
        "api_calls": 1,
        "error_count": 0,
    }


def test_fee_importer_counts_failed_batch(session):
    records = [FakeRecord(123), FakeRecord(456)]
    ciagle = FakePublicationClass("Wydawnictwo_Ciagle", records)
    zwarte = FakePublicationClass("Wydawnictwo_Zwarte", [])
    client = MagicMock()
    client.get_publication_fees_batch.side_effect = RuntimeError("fee API failed")
    importer = FeeImporter(session, client=client)

    with patch("pbn_import.utils.fee_import.Wydawnictwo_Ciagle", ciagle):
        with patch("pbn_import.utils.fee_import.Wydawnictwo_Zwarte", zwarte):
            with patch.object(importer, "handle_error") as handle_error:
                result = importer.run()

    handle_error.assert_called_once()
    assert result["fees_imported"] == 0
    assert result["fees_failed"] == 2
    assert result["api_calls"] == 0


def test_statement_importer_returns_when_publication_setup_missing(session):
    importer = StatementImporter(session, client=MagicMock(), uczelnia=None)

    with patch.object(importer, "create_subtask_progress", return_value=MagicMock()):
        with patch(
            "pbn_import.utils.statement_import.pobierz_oswiadczenia_z_instytucji"
        ):
            with patch.object(
                importer.publication_importer,
                "_setup_uczelnia_and_jednostka",
                return_value=None,
            ):
                result = importer.run()

    assert result == {
        "statements_imported": False,
        "reason": "No Uczelnia PBN UID",
    }


def test_statement_importer_full_success_logs_inconsistency_summary(
    session,
    uczelnia,
):
    importer = StatementImporter(session, client=MagicMock(), uczelnia=uczelnia)
    default_jednostka = baker.make(Jednostka, uczelnia=uczelnia)
    importer.publication_importer.default_jednostka = default_jednostka

    def integrate_with_inconsistency(**kwargs):
        kwargs["inconsistency_callback"](
            "author_not_found",
            pbn_publication=SimpleNamespace(mongoId="pub-1", title="PBN title"),
            message="missing author",
        )

    with patch.object(importer, "create_subtask_progress", return_value=MagicMock()):
        with patch(
            "pbn_import.utils.statement_import.pobierz_oswiadczenia_z_instytucji"
        ):
            with patch.object(
                importer.publication_importer,
                "_setup_uczelnia_and_jednostka",
                return_value=uczelnia,
            ):
                with patch.object(
                    importer,
                    "_download_missing_publications",
                    return_value={"downloaded": 1, "failed": 0, "errors": []},
                ):
                    with patch(
                        "pbn_import.utils.statement_import."
                        "integruj_oswiadczenia_z_instytucji",
                        side_effect=integrate_with_inconsistency,
                    ) as integrate:
                        result = importer.run()

    integrate.assert_called_once_with(
        missing_publication_callback=None,
        inconsistency_callback=integrate.call_args.kwargs["inconsistency_callback"],
        default_jednostka=default_jednostka,
        uczelnia=uczelnia,
    )
    assert result == {"statements_imported": True, "error_count": 0}
    assert session.inconsistencies.count() == 1
    assert ImportLog.objects.filter(
        session=session,
        level="warning",
        message__contains="Znaleziono 1 nieścisłości",
    ).exists()
    assert ImportLog.objects.filter(
        session=session,
        level="success",
        message="Oświadczenia zintegrowane pomyślnie",
    ).exists()


def test_statement_importer_records_download_and_integration_errors(session, uczelnia):
    importer = StatementImporter(session, client=MagicMock(), uczelnia=uczelnia)
    importer.publication_importer.default_jednostka = baker.make(
        Jednostka, uczelnia=uczelnia
    )

    with patch.object(importer, "create_subtask_progress", return_value=MagicMock()):
        with patch(
            "pbn_import.utils.statement_import.pobierz_oswiadczenia_z_instytucji",
            side_effect=RuntimeError("download failed"),
        ):
            with patch.object(
                importer.publication_importer,
                "_setup_uczelnia_and_jednostka",
                return_value=uczelnia,
            ):
                with patch.object(
                    importer,
                    "_download_missing_publications",
                    return_value={"downloaded": 0, "failed": 0, "errors": []},
                ):
                    with patch(
                        "pbn_import.utils.statement_import."
                        "integruj_oswiadczenia_z_instytucji",
                        side_effect=RuntimeError("integration failed"),
                    ):
                        with patch(
                            "pbn_import.utils.base.rollbar.report_exc_info"
                        ) as report_exc_info:
                            result = importer.run()

    assert report_exc_info.call_count == 2
    assert result == {"statements_imported": True, "error_count": 2}
    assert importer.errors == [
        "Nie udało się pobrać oświadczeń: download failed",
        "Nie udało się zintegrować oświadczeń: integration failed",
    ]
    assert (
        list(
            ImportLog.objects.filter(session=session, level="error")
            .order_by("pk")
            .values_list("message", flat=True)
        )
        == importer.errors
    )


def test_statement_download_missing_publications_no_statement_ids(session):
    importer = StatementImporter(session, client=MagicMock(), uczelnia=None)

    with patch(
        "pbn_import.utils.statement_import.OswiadczenieInstytucji.objects"
    ) as statements:
        statements.values_list.return_value.distinct.return_value = []

        assert importer._download_missing_publications(MagicMock()) is None


def test_statement_download_missing_publications_no_missing_publications(session):
    importer = StatementImporter(session, client=MagicMock(), uczelnia=None)

    with patch(
        "pbn_import.utils.statement_import.OswiadczenieInstytucji.objects"
    ) as statements:
        with patch("pbn_import.utils.statement_import.Rekord.objects") as rekordy:
            statements.values_list.return_value.distinct.return_value = ["pub-1"]
            rekordy.exclude.return_value.values_list.return_value = ["pub-1"]

            result = importer._download_missing_publications(MagicMock())

    assert result == {"downloaded": 0, "failed": 0, "errors": []}


def test_statement_download_missing_publications_downloads_and_logs_errors(session):
    importer = StatementImporter(session, client=MagicMock(), uczelnia=None)
    default_jednostka = baker.make(Jednostka)

    with patch(
        "pbn_import.utils.statement_import.OswiadczenieInstytucji.objects"
    ) as statements:
        with patch("pbn_import.utils.statement_import.Rekord.objects") as rekordy:
            with patch.object(
                importer, "create_subtask_progress", return_value=MagicMock()
            ):
                with patch(
                    "pbn_import.utils.statement_import."
                    "pobierz_brakujace_publikacje_batch",
                    return_value={
                        "downloaded": 1,
                        "failed": 1,
                        "errors": ["missing pub failed"],
                    },
                ) as download:
                    statements.values_list.return_value.distinct.return_value = [
                        "pub-1",
                        "pub-2",
                    ]
                    rekordy.objects = rekordy
                    rekordy.exclude.return_value.values_list.return_value = ["pub-1"]

                    result = importer._download_missing_publications(default_jednostka)

    download.assert_called_once_with(
        client=importer.client,
        missing_pbn_uids={"pub-2"},
        default_jednostka=default_jednostka,
        max_workers=8,
        callback=download.call_args.kwargs["callback"],
    )
    assert result["downloaded"] == 1
    assert ImportLog.objects.filter(
        session=session, level="warning", message__contains="missing pub failed"
    ).exists()


def test_statement_download_missing_publications_handles_batch_error(session):
    importer = StatementImporter(session, client=MagicMock(), uczelnia=None)

    with patch(
        "pbn_import.utils.statement_import.OswiadczenieInstytucji.objects"
    ) as statements:
        with patch("pbn_import.utils.statement_import.Rekord.objects") as rekordy:
            with patch.object(
                importer, "create_subtask_progress", return_value=MagicMock()
            ):
                with patch.object(importer, "clear_subtask_progress") as clear:
                    with patch(
                        "pbn_import.utils.statement_import."
                        "pobierz_brakujace_publikacje_batch",
                        side_effect=RuntimeError("batch failed"),
                    ):
                        with patch(
                            "pbn_import.utils.base.rollbar.report_exc_info"
                        ) as report_exc_info:
                            statements.values_list.return_value.distinct.return_value = [
                                "pub-1"
                            ]
                            rekordy.exclude.return_value.values_list.return_value = []

                            result = importer._download_missing_publications(
                                MagicMock()
                            )

    assert result is None
    report_exc_info.assert_called_once()
    assert importer.errors == [
        "Nie udało się pobrać brakujących publikacji: batch failed"
    ]
    assert ImportLog.objects.filter(
        session=session,
        level="error",
        message="Nie udało się pobrać brakujących publikacji: batch failed",
    ).exists()
    clear.assert_called_once_with()


def test_statement_inconsistency_callback_creates_record(session):
    importer = StatementImporter(session, client=MagicMock(), uczelnia=None)
    callback = importer._create_inconsistency_callback()
    pbn_publication = SimpleNamespace(mongoId="pub-1", title="PBN publication")
    pbn_author = SimpleNamespace(pk="author-1", lastName="Kowalski", name="Jan")

    callback(
        "author_not_found",
        pbn_publication=pbn_publication,
        pbn_author=pbn_author,
        discipline="2.3",
        message="missing author",
        action_taken="reported",
    )

    inconsistency = session.inconsistencies.get()
    assert inconsistency.inconsistency_type == "author_not_found"
    assert inconsistency.pbn_publication_id == "pub-1"
    assert inconsistency.pbn_author_name == "Kowalski Jan"
    assert inconsistency.message == "missing author"


def test_statement_inconsistency_callback_records_bpp_publication_details(session):
    importer = StatementImporter(session, client=MagicMock(), uczelnia=None)
    callback = importer._create_inconsistency_callback()
    content_type = baker.make("contenttypes.ContentType")
    bpp_publication = SimpleNamespace(pk=123, tytul_oryginalny="BPP title")
    bpp_author = SimpleNamespace(pk=456, __str__=lambda self: "BPP author")

    with patch(
        "pbn_import.utils.statement_import.ContentType.objects.get_for_model",
        return_value=content_type,
    ):
        callback(
            "publication_not_found",
            bpp_publication=bpp_publication,
            bpp_author=bpp_author,
            message="publication mismatch",
        )

    inconsistency = session.inconsistencies.get()
    assert inconsistency.bpp_publication_id == 123
    assert inconsistency.bpp_publication_content_type == content_type
    assert inconsistency.bpp_publication_title == "BPP title"
    assert inconsistency.bpp_author_id == 456


def test_statement_inconsistency_callback_logs_persistence_failure(session):
    importer = StatementImporter(session, client=MagicMock(), uczelnia=None)
    callback = importer._create_inconsistency_callback()

    with patch.object(
        ImportInconsistency.objects,
        "create",
        side_effect=RuntimeError("cannot save inconsistency"),
    ):
        callback("author_not_found", message="broken")

    assert ImportLog.objects.filter(
        session=session,
        level="warning",
        message__contains="Błąd podczas zapisu nieścisłości",
    ).exists()
