"""Tests for shared PBN import command helpers."""

from unittest.mock import MagicMock, patch

import pytest
from django.core.management import CommandError
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia
from pbn_api.exceptions import HttpException
from pbn_import.utils.command_helpers import (
    get_validated_default_jednostka,
    import_publication_with_statements,
)


@pytest.mark.django_db
def test_get_validated_default_jednostka_uses_explicit_unit_name():
    uczelnia = baker.make(Uczelnia)
    jednostka = baker.make(Jednostka, nazwa="Chosen unit", uczelnia=uczelnia)

    assert get_validated_default_jednostka("Chosen unit", uczelnia) == jednostka


@pytest.mark.django_db
def test_get_validated_default_jednostka_rejects_missing_explicit_unit():
    uczelnia = baker.make(Uczelnia)

    with pytest.raises(CommandError, match="nie istnieje"):
        get_validated_default_jednostka("Missing unit", uczelnia)


def test_get_validated_default_jednostka_rejects_missing_or_ambiguous_uczelnia():
    with patch(
        "pbn_import.utils.command_helpers.Uczelnia.objects.count", return_value=0
    ):
        with pytest.raises(CommandError, match="Brak uczelni"):
            get_validated_default_jednostka()

    with patch(
        "pbn_import.utils.command_helpers.Uczelnia.objects.count", return_value=2
    ):
        with pytest.raises(CommandError, match="więcej niż jedna uczelnia"):
            get_validated_default_jednostka()


@pytest.mark.django_db
def test_get_validated_default_jednostka_creates_default_for_single_uczelnia():
    uczelnia = baker.make(Uczelnia)
    default = baker.make(Jednostka, uczelnia=uczelnia)

    with patch(
        "pbn_import.utils.command_helpers.Uczelnia.objects.count", return_value=1
    ):
        with patch(
            "pbn_import.utils.command_helpers.Uczelnia.objects.get",
            return_value=uczelnia,
        ):
            with patch(
                "pbn_import.utils.command_helpers.znajdz_lub_utworz_jednostke_domyslna",
                return_value=(default, False),
            ):
                assert get_validated_default_jednostka() == default


def test_import_publication_with_statements_success():
    publication = MagicMock()
    client = MagicMock()
    default_jednostka = MagicMock()

    with patch(
        "pbn_import.utils.command_helpers.importuj_publikacje_po_pbn_uid_id",
        return_value=publication,
    ) as import_publication:
        with patch(
            "pbn_import.utils.command_helpers."
            "importuj_oswiadczenia_pojedynczej_publikacji",
            return_value=(3, 2),
        ) as import_statements:
            result = import_publication_with_statements(
                "pbn-1",
                client,
                default_jednostka,
                force=True,
                rodzaj_periodyk="periodical",
                dyscypliny_cache={"2.3": "disc"},
                inconsistency_callback="callback",
            )

    assert result == (publication, None, (3, 2))
    import_publication.assert_called_once_with(
        "pbn-1",
        client=client,
        default_jednostka=default_jednostka,
        force=True,
        rodzaj_periodyk="periodical",
        dyscypliny_cache={"2.3": "disc"},
        inconsistency_callback="callback",
    )
    import_statements.assert_called_once_with(
        client,
        "pbn-1",
        default_jednostka=default_jednostka,
        inconsistency_callback="callback",
    )


def test_import_publication_with_statements_skips_statements_when_disabled():
    with patch(
        "pbn_import.utils.command_helpers.importuj_publikacje_po_pbn_uid_id",
        return_value=MagicMock(),
    ):
        with patch(
            "pbn_import.utils.command_helpers."
            "importuj_oswiadczenia_pojedynczej_publikacji"
        ) as import_statements:
            result, error_info, statement_counts = import_publication_with_statements(
                "pbn-1",
                MagicMock(),
                MagicMock(),
                with_statements=False,
            )

    assert result is not None
    assert error_info is None
    assert statement_counts is None
    import_statements.assert_not_called()


def test_import_publication_with_statements_keeps_publication_on_statement_http_error():
    publication = MagicMock()

    with patch(
        "pbn_import.utils.command_helpers.importuj_publikacje_po_pbn_uid_id",
        return_value=publication,
    ):
        with patch(
            "pbn_import.utils.command_helpers."
            "importuj_oswiadczenia_pojedynczej_publikacji",
            side_effect=HttpException(404, "https://pbn.example.test", "not found"),
        ):
            result, error_info, statement_counts = import_publication_with_statements(
                "pbn-1",
                MagicMock(),
                MagicMock(),
            )

    assert result == publication
    assert error_info == {
        "message": "Publikacja OK, błąd oświadczeń: HTTP 404",
        "traceback": None,
    }
    assert statement_counts is None


def test_import_publication_with_statements_reports_publication_http_error():
    with patch(
        "pbn_import.utils.command_helpers.importuj_publikacje_po_pbn_uid_id",
        side_effect=HttpException(500, "https://pbn.example.test", "server exploded"),
    ):
        result, error_info, statement_counts = import_publication_with_statements(
            "pbn-1",
            MagicMock(),
            MagicMock(),
        )

    assert result is None
    assert "HTTP 500: server exploded" in error_info["message"]
    assert "traceback" in error_info
    assert statement_counts is None


def test_import_publication_with_statements_reports_generic_error():
    with patch(
        "pbn_import.utils.command_helpers.importuj_publikacje_po_pbn_uid_id",
        side_effect=RuntimeError("bad import"),
    ):
        result, error_info, statement_counts = import_publication_with_statements(
            "pbn-1",
            MagicMock(),
            MagicMock(),
        )

    assert result is None
    assert error_info["message"] == "bad import"
    assert "traceback" in error_info
    assert statement_counts is None
