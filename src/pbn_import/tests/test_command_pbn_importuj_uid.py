"""Tests for pbn_importuj_uid management command."""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia, Wydawnictwo_Ciagle


@pytest.fixture
def uczelnia_with_pbn_config(db):
    """Create Uczelnia with PBN integration config."""
    uczelnia = Uczelnia.objects.first()
    if uczelnia is None:
        uczelnia = baker.make(Uczelnia)

    uczelnia.pbn_integracja = True
    uczelnia.pbn_app_name = "test-app-id"
    uczelnia.pbn_app_token = "test-app-token"
    uczelnia.pbn_api_root = "https://pbn-test.example.com"
    uczelnia.save()

    # Ensure obca_jednostka exists
    if uczelnia.obca_jednostka is None:
        obca = baker.make(
            Jednostka,
            uczelnia=uczelnia,
            nazwa="Obca jednostka",
            skupia_pracownikow=False,
        )
        uczelnia.obca_jednostka = obca
        uczelnia.save()

    return uczelnia


@pytest.fixture
def default_jednostka(uczelnia_with_pbn_config):
    """Create default jednostka for import."""
    jednostka, _ = Jednostka.objects.get_or_create(
        nazwa="Jednostka Domyślna",
        defaults={
            "skrot": "JD",
            "uczelnia": uczelnia_with_pbn_config,
        },
    )
    return jednostka


@pytest.fixture
def mock_imported_publication(db, uczelnia_with_pbn_config):
    """Create a mock imported publication."""
    return baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test Publication",
        rok=2024,
    )


@pytest.mark.django_db
class TestPbnImportujUidCommand:
    """Tests for pbn_importuj_uid command."""

    def test_requires_pbn_uid_argument(self, uczelnia_with_pbn_config):
        """Command should require at least one PBN UID argument."""
        stdout = StringIO()
        stderr = StringIO()

        with pytest.raises(CommandError, match="pbn_uids"):
            call_command(
                "pbn_importuj_uid",
                stdout=stdout,
                stderr=stderr,
            )

    def test_fails_without_uczelnia(self, db):
        """Command should fail if no default Uczelnia exists."""
        Uczelnia.objects.all().delete()

        stdout = StringIO()
        stderr = StringIO()

        with pytest.raises(CommandError, match="Brak domyślnej uczelni"):
            with patch(
                "pbn_import.management.commands.pbn_importuj_uid."
                "PBNBaseCommand.get_client"
            ):
                call_command(
                    "pbn_importuj_uid",
                    "test-uid",
                    stdout=stdout,
                    stderr=stderr,
                )

    def test_fails_with_nonexistent_jednostka(self, uczelnia_with_pbn_config):
        """Command should fail if specified jednostka doesn't exist."""
        stdout = StringIO()
        stderr = StringIO()

        with pytest.raises(CommandError, match="nie istnieje"):
            with patch(
                "pbn_import.management.commands.pbn_importuj_uid."
                "PBNBaseCommand.get_client"
            ):
                call_command(
                    "pbn_importuj_uid",
                    "test-uid",
                    "--jednostka",
                    "Nieistniejąca Jednostka",
                    stdout=stdout,
                    stderr=stderr,
                )

    def test_successful_import(
        self,
        uczelnia_with_pbn_config,
        default_jednostka,
        mock_imported_publication,
    ):
        """Command should successfully import a publication."""
        stdout = StringIO()
        stderr = StringIO()

        with patch(
            "pbn_import.management.commands.pbn_importuj_uid.PBNBaseCommand.get_client"
        ):
            with patch(
                "pbn_import.management.commands.pbn_importuj_uid."
                "import_publication_with_statements"
            ) as mock_import:
                mock_import.return_value = (mock_imported_publication, None, None)

                call_command(
                    "pbn_importuj_uid",
                    "test-pbn-uid",
                    stdout=stdout,
                    stderr=stderr,
                )

        output = stdout.getvalue()
        assert "OK: Test Publication" in output
        assert "2024" in output
        assert "Zaimportowano: 1" in output

    def test_handles_http_exception(self, uczelnia_with_pbn_config, default_jednostka):
        """Command should handle HTTP exceptions gracefully."""
        stdout = StringIO()
        stderr = StringIO()

        with patch(
            "pbn_import.management.commands.pbn_importuj_uid.PBNBaseCommand.get_client"
        ):
            with patch(
                "pbn_import.management.commands.pbn_importuj_uid.import_publication_with_statements"
            ) as mock_import:
                mock_import.return_value = (
                    None,
                    {"message": "HTTP 404: Publication not found", "traceback": None},
                    None,
                )

                call_command(
                    "pbn_importuj_uid",
                    "nonexistent-uid",
                    stdout=stdout,
                    stderr=stderr,
                )

        error_output = stderr.getvalue()
        assert "HTTP 404" in error_output
        assert "Błędów: 1" in stdout.getvalue()

    def test_handles_none_result(self, uczelnia_with_pbn_config, default_jednostka):
        """Command should handle None result from import function."""
        stdout = StringIO()
        stderr = StringIO()

        with patch(
            "pbn_import.management.commands.pbn_importuj_uid.PBNBaseCommand.get_client"
        ):
            with patch(
                "pbn_import.management.commands.pbn_importuj_uid.import_publication_with_statements"
            ) as mock_import:
                mock_import.return_value = (None, None, None)

                call_command(
                    "pbn_importuj_uid",
                    "test-uid",
                    stdout=stdout,
                    stderr=stderr,
                )

        error_output = stderr.getvalue()
        assert "nie zwrócił wyniku" in error_output

    def test_multiple_uids(
        self,
        uczelnia_with_pbn_config,
        default_jednostka,
        mock_imported_publication,
    ):
        """Command should handle multiple UIDs."""
        stdout = StringIO()
        stderr = StringIO()

        with patch(
            "pbn_import.management.commands.pbn_importuj_uid.PBNBaseCommand.get_client"
        ):
            with patch(
                "pbn_import.management.commands.pbn_importuj_uid.import_publication_with_statements"
            ) as mock_import:
                mock_import.return_value = (mock_imported_publication, None, None)

                call_command(
                    "pbn_importuj_uid",
                    "uid1",
                    "uid2",
                    "uid3",
                    stdout=stdout,
                    stderr=stderr,
                )

        assert mock_import.call_count == 3
        assert "Zaimportowano: 3" in stdout.getvalue()

    def test_force_flag_passed_to_import(
        self,
        uczelnia_with_pbn_config,
        default_jednostka,
        mock_imported_publication,
    ):
        """Command should pass force flag to import function."""
        stdout = StringIO()
        stderr = StringIO()

        with patch(
            "pbn_import.management.commands.pbn_importuj_uid.PBNBaseCommand.get_client"
        ):
            with patch(
                "pbn_import.management.commands.pbn_importuj_uid.import_publication_with_statements"
            ) as mock_import:
                mock_import.return_value = (mock_imported_publication, None, None)

                call_command(
                    "pbn_importuj_uid",
                    "test-uid",
                    "--force",
                    stdout=stdout,
                    stderr=stderr,
                )

        mock_import.assert_called_once()
        call_kwargs = mock_import.call_args[1]
        assert call_kwargs["force"] is True

    def test_with_oswiadczenia_flag(
        self,
        uczelnia_with_pbn_config,
        default_jednostka,
        mock_imported_publication,
    ):
        """Command should import statements when flag is set."""
        stdout = StringIO()
        stderr = StringIO()

        with patch(
            "pbn_import.management.commands.pbn_importuj_uid.PBNBaseCommand.get_client"
        ):
            with patch(
                "pbn_import.management.commands.pbn_importuj_uid.import_publication_with_statements"
            ) as mock_import:
                mock_import.return_value = (
                    mock_imported_publication,
                    None,
                    (5, 3),  # Pobrano 5, zintegrowano 3
                )

                call_command(
                    "pbn_importuj_uid",
                    "test-uid",
                    "--with-oswiadczenia",
                    stdout=stdout,
                    stderr=stderr,
                )

        mock_import.assert_called_once()
        call_kwargs = mock_import.call_args[1]
        assert call_kwargs["with_statements"] is True

        output = stdout.getvalue()
        assert "Oświadczeń: pobrano 5, zintegrowano 3" in output

    def test_custom_jednostka(
        self,
        uczelnia_with_pbn_config,
        mock_imported_publication,
    ):
        """Command should use custom jednostka when specified."""
        custom_jednostka = baker.make(
            Jednostka,
            nazwa="Katedra Testowa",
            uczelnia=uczelnia_with_pbn_config,
        )

        stdout = StringIO()
        stderr = StringIO()

        with patch(
            "pbn_import.management.commands.pbn_importuj_uid.PBNBaseCommand.get_client"
        ):
            with patch(
                "pbn_import.management.commands.pbn_importuj_uid.import_publication_with_statements"
            ) as mock_import:
                mock_import.return_value = (mock_imported_publication, None, None)

                call_command(
                    "pbn_importuj_uid",
                    "test-uid",
                    "--jednostka",
                    "Katedra Testowa",
                    stdout=stdout,
                    stderr=stderr,
                )

        # Sprawdź że import został wywołany z odpowiednią jednostką
        mock_import.assert_called_once()
        # Jednostka jest przekazana jako drugi argument pozycyjny
        call_args = mock_import.call_args[0]
        assert call_args[2] == custom_jednostka

    def test_inconsistency_callback_collects_messages(
        self, uczelnia_with_pbn_config, default_jednostka, mock_imported_publication
    ):
        """Command should collect and display inconsistency messages."""
        stdout = StringIO()
        stderr = StringIO()

        def mock_import_side_effect(
            pbn_uid,
            client,
            default_jednostka,
            force=False,
            with_statements=False,
            inconsistency_callback=None,
            **kwargs,
        ):
            # Simulate inconsistency being reported
            if inconsistency_callback:
                inconsistency_callback(
                    inconsistency_type="test_inconsistency",
                    message="Test inconsistency message",
                )
            return (mock_imported_publication, None, None)

        with patch(
            "pbn_import.management.commands.pbn_importuj_uid.PBNBaseCommand.get_client"
        ):
            with patch(
                "pbn_import.management.commands.pbn_importuj_uid.import_publication_with_statements",
                side_effect=mock_import_side_effect,
            ):
                call_command(
                    "pbn_importuj_uid",
                    "test-uid",
                    stdout=stdout,
                    stderr=stderr,
                )

        output = stdout.getvalue()
        assert "Niespójności:" in output
        assert "[test_inconsistency]" in output

    def test_dry_run_displays_publication_info(self, uczelnia_with_pbn_config):
        """Command with --dry-run should display publication info without importing."""
        stdout = StringIO()
        stderr = StringIO()

        mock_pbn_publication = MagicMock()
        mock_pbn_publication.title = "Test Article Title"
        mock_pbn_publication.year = 2023
        mock_pbn_publication.type.return_value = "ARTICLE"
        mock_pbn_publication.doi = "10.1234/test"
        mock_pbn_publication.isbn = ""
        mock_pbn_publication.autorzy = {
            "authors": [
                {"familyName": "Kowalski", "givenNames": "Jan"},
                {"familyName": "Nowak", "givenNames": "Anna"},
            ]
        }
        mock_pbn_publication.policz_autorow.return_value = 2
        mock_pbn_publication.rekord_w_bpp = None

        with patch(
            "pbn_import.management.commands.pbn_importuj_uid.PBNBaseCommand.get_client"
        ):
            with patch(
                "pbn_import.management.commands.pbn_importuj_uid."
                "get_or_download_publication"
            ) as mock_get:
                mock_get.return_value = mock_pbn_publication

                call_command(
                    "pbn_importuj_uid",
                    "test-uid",
                    "--dry-run",
                    stdout=stdout,
                    stderr=stderr,
                )

        output = stdout.getvalue()
        assert "Sprawdzam: test-uid" in output
        assert "Test Article Title" in output
        assert "2023" in output
        assert "ARTICLE" in output
        assert "10.1234/test" in output
        assert "Kowalski Jan" in output
        assert "Nowak Anna" in output
        assert "Sprawdzono: 1" in output

    def test_dry_run_shows_existing_bpp_record(self, uczelnia_with_pbn_config):
        """Command with --dry-run should indicate if record exists in BPP."""
        stdout = StringIO()
        stderr = StringIO()

        mock_bpp_record = MagicMock()
        mock_bpp_record.pk = 12345
        mock_bpp_record.__str__ = MagicMock(return_value="Existing Publication")

        mock_pbn_publication = MagicMock()
        mock_pbn_publication.title = "Test Title"
        mock_pbn_publication.year = 2023
        mock_pbn_publication.type.return_value = "BOOK"
        mock_pbn_publication.doi = ""
        mock_pbn_publication.isbn = "978-83-12345-67-8"
        mock_pbn_publication.autorzy = {}
        mock_pbn_publication.rekord_w_bpp = mock_bpp_record

        with patch(
            "pbn_import.management.commands.pbn_importuj_uid.PBNBaseCommand.get_client"
        ):
            with patch(
                "pbn_import.management.commands.pbn_importuj_uid."
                "get_or_download_publication"
            ) as mock_get:
                mock_get.return_value = mock_pbn_publication

                call_command(
                    "pbn_importuj_uid",
                    "test-uid",
                    "--dry-run",
                    stdout=stdout,
                    stderr=stderr,
                )

        output = stdout.getvalue()
        assert "Istnieje w BPP" in output
        assert "12345" in output

    def test_dry_run_does_not_call_import(self, uczelnia_with_pbn_config):
        """Command with --dry-run should not call import function."""
        stdout = StringIO()
        stderr = StringIO()

        mock_pbn_publication = MagicMock()
        mock_pbn_publication.title = "Test"
        mock_pbn_publication.year = 2023
        mock_pbn_publication.type.return_value = "ARTICLE"
        mock_pbn_publication.doi = ""
        mock_pbn_publication.isbn = ""
        mock_pbn_publication.autorzy = {}
        mock_pbn_publication.rekord_w_bpp = None

        with patch(
            "pbn_import.management.commands.pbn_importuj_uid.PBNBaseCommand.get_client"
        ):
            with patch(
                "pbn_import.management.commands.pbn_importuj_uid."
                "get_or_download_publication"
            ) as mock_get:
                mock_get.return_value = mock_pbn_publication

                with patch(
                    "pbn_import.utils.command_helpers."
                    "import_publication_with_statements"
                ) as mock_import:
                    call_command(
                        "pbn_importuj_uid",
                        "test-uid",
                        "--dry-run",
                        stdout=stdout,
                        stderr=stderr,
                    )

                    # Import should NOT be called in dry-run mode
                    mock_import.assert_not_called()
