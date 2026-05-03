"""Tests for the ``ustaw_daty_oswiadczenia_pbn`` management command.

Wydzielone z ``test_management_commands.py``, by trzymać per-komendę
spójne grupy testów w plikach <850 linii.
"""

import pytest
from django.core.management import call_command


@pytest.mark.django_db
class TestUstawDatyOswiadczeniaPbnCommand:
    """Test ustaw_daty_oswiadczenia_pbn management command."""

    def test_basic_single_year_with_default_date(
        self, wydawnictwo_ciagle, autor_jan_kowalski, jednostka
    ):
        """Test setting default date for single year 2024."""
        from datetime import date

        wydawnictwo_ciagle.rok = 2024
        wydawnictwo_ciagle.save()

        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = None
        wca.save()

        call_command("ustaw_daty_oswiadczenia_pbn", "--rok", "2024")

        wca.refresh_from_db()
        assert wca.data_oswiadczenia == date(2024, 12, 31)

    def test_single_year_2022_gets_correct_default_date(
        self, wydawnictwo_ciagle, autor_jan_kowalski, jednostka
    ):
        """Test that year 2022 gets 30.12.2022 as default date."""
        from datetime import date

        wydawnictwo_ciagle.rok = 2022
        wydawnictwo_ciagle.save()

        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = None
        wca.save()

        call_command("ustaw_daty_oswiadczenia_pbn", "--rok", "2022")

        wca.refresh_from_db()
        assert wca.data_oswiadczenia == date(2022, 12, 30)

    def test_single_year_2023_gets_correct_default_date(
        self, wydawnictwo_ciagle, autor_jan_kowalski, jednostka
    ):
        """Test that year 2023 gets 29.12.2023 as default date."""
        from datetime import date

        wydawnictwo_ciagle.rok = 2023
        wydawnictwo_ciagle.save()

        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = None
        wca.save()

        call_command("ustaw_daty_oswiadczenia_pbn", "--rok", "2023")

        wca.refresh_from_db()
        assert wca.data_oswiadczenia == date(2023, 12, 29)

    def test_year_range_with_rok_min_rok_max(
        self, wydawnictwo_ciagle, wydawnictwo_zwarte, autor_jan_kowalski, jednostka
    ):
        """Test setting dates for year range."""
        from datetime import date

        wydawnictwo_ciagle.rok = 2022
        wydawnictwo_ciagle.save()

        wydawnictwo_zwarte.rok = 2024
        wydawnictwo_zwarte.save()

        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = None
        wca.save()

        wza = wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
        wza.data_oswiadczenia = None
        wza.save()

        call_command(
            "ustaw_daty_oswiadczenia_pbn", "--rok-min", "2022", "--rok-max", "2025"
        )

        wca.refresh_from_db()
        wza.refresh_from_db()

        assert wca.data_oswiadczenia == date(2022, 12, 30)
        assert wza.data_oswiadczenia == date(2024, 12, 31)

    def test_explicit_date_overrides_defaults(
        self, wydawnictwo_ciagle, autor_jan_kowalski, jednostka
    ):
        """Test that explicit date is used instead of defaults."""
        from datetime import date

        wydawnictwo_ciagle.rok = 2024
        wydawnictwo_ciagle.save()

        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = None
        wca.save()

        call_command(
            "ustaw_daty_oswiadczenia_pbn",
            "--rok",
            "2024",
            "--data-oswiadczenia",
            "15.06.2024",
        )

        wca.refresh_from_db()
        assert wca.data_oswiadczenia == date(2024, 6, 15)

    def test_use_record_creation_date(
        self, wydawnictwo_ciagle, autor_jan_kowalski, jednostka
    ):
        """Test using record creation date as source."""
        wydawnictwo_ciagle.rok = 2024
        wydawnictwo_ciagle.save()

        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = None
        wca.save()

        call_command(
            "ustaw_daty_oswiadczenia_pbn",
            "--rok",
            "2024",
            "--uzyj-daty-utworzenia-rekordu",
        )

        wca.refresh_from_db()
        expected_date = wydawnictwo_ciagle.utworzono.date()
        assert wca.data_oswiadczenia == expected_date

    def test_use_record_modification_date(
        self, wydawnictwo_ciagle, autor_jan_kowalski, jednostka
    ):
        """Test using record modification date as source."""
        wydawnictwo_ciagle.rok = 2024
        wydawnictwo_ciagle.save()

        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = None
        wca.save()

        call_command(
            "ustaw_daty_oswiadczenia_pbn",
            "--rok",
            "2024",
            "--uzyj-daty-ostatniej-modyfikacji-rekordu",
        )

        wca.refresh_from_db()
        expected_date = wydawnictwo_ciagle.ostatnio_zmieniony.date()
        assert wca.data_oswiadczenia == expected_date

    def test_dry_run_does_not_modify_data(
        self, wydawnictwo_ciagle, autor_jan_kowalski, jednostka
    ):
        """Test that dry-run mode does not save changes."""
        from django.db import transaction

        wydawnictwo_ciagle.rok = 2024
        wydawnictwo_ciagle.save()

        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = None
        wca.save()

        # Dry run raises TransactionManagementError to roll back
        with pytest.raises(transaction.TransactionManagementError):
            call_command("ustaw_daty_oswiadczenia_pbn", "--rok", "2024", "--dry-run")

        wca.refresh_from_db()
        assert wca.data_oswiadczenia is None

    def test_skips_records_with_existing_date(
        self, wydawnictwo_ciagle, autor_jan_kowalski, jednostka
    ):
        """Test that records with existing date are not modified."""
        from datetime import date

        wydawnictwo_ciagle.rok = 2024
        wydawnictwo_ciagle.save()

        existing_date = date(2020, 5, 15)
        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = existing_date
        wca.save()

        call_command("ustaw_daty_oswiadczenia_pbn", "--rok", "2024")

        wca.refresh_from_db()
        assert wca.data_oswiadczenia == existing_date

    def test_rok_with_rok_min_fails(self):
        """Test that using --rok with --rok-min raises error."""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError) as exc_info:
            call_command(
                "ustaw_daty_oswiadczenia_pbn", "--rok", "2024", "--rok-min", "2022"
            )

        assert "Nie można używać --rok razem z --rok-min/--rok-max" in str(
            exc_info.value
        )

    def test_rok_min_without_rok_max_fails(self):
        """Test that using --rok-min without --rok-max raises error."""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError) as exc_info:
            call_command("ustaw_daty_oswiadczenia_pbn", "--rok-min", "2022")

        assert "muszą być używane razem" in str(exc_info.value)

    def test_rok_max_without_rok_min_fails(self):
        """Test that using --rok-max without --rok-min raises error."""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError) as exc_info:
            call_command("ustaw_daty_oswiadczenia_pbn", "--rok-max", "2025")

        assert "muszą być używane razem" in str(exc_info.value)

    def test_rok_min_greater_than_rok_max_fails(self):
        """Test that --rok-min > --rok-max raises error."""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError) as exc_info:
            call_command(
                "ustaw_daty_oswiadczenia_pbn", "--rok-min", "2025", "--rok-max", "2022"
            )

        assert "nie może być większy" in str(exc_info.value)

    def test_year_outside_defaults_without_explicit_date_fails(self):
        """Test that year outside 2022-2025 without explicit date raises error."""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError) as exc_info:
            call_command("ustaw_daty_oswiadczenia_pbn", "--rok", "2020")

        assert "Brak domyślnej daty oświadczenia dla lat: 2020" in str(exc_info.value)

    def test_year_outside_defaults_with_explicit_date_works(
        self, wydawnictwo_ciagle, autor_jan_kowalski, jednostka
    ):
        """Test that year outside defaults works with explicit date."""
        from datetime import date

        wydawnictwo_ciagle.rok = 2020
        wydawnictwo_ciagle.save()

        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = None
        wca.save()

        call_command(
            "ustaw_daty_oswiadczenia_pbn",
            "--rok",
            "2020",
            "--data-oswiadczenia",
            "31.12.2020",
        )

        wca.refresh_from_db()
        assert wca.data_oswiadczenia == date(2020, 12, 31)

    def test_year_outside_defaults_with_creation_date_works(
        self, wydawnictwo_ciagle, autor_jan_kowalski, jednostka
    ):
        """Test that year outside defaults works with creation date option."""
        wydawnictwo_ciagle.rok = 2020
        wydawnictwo_ciagle.save()

        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = None
        wca.save()

        call_command(
            "ustaw_daty_oswiadczenia_pbn",
            "--rok",
            "2020",
            "--uzyj-daty-utworzenia-rekordu",
        )

        wca.refresh_from_db()
        expected_date = wydawnictwo_ciagle.utworzono.date()
        assert wca.data_oswiadczenia == expected_date

    def test_invalid_date_format_fails(self):
        """Test that invalid date format raises error."""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError) as exc_info:
            call_command(
                "ustaw_daty_oswiadczenia_pbn",
                "--rok",
                "2024",
                "--data-oswiadczenia",
                "2024-12-31",
            )

        assert "Nieprawidłowy format daty" in str(exc_info.value)
        assert "DD.MM.RRRR" in str(exc_info.value)

    def test_no_arguments_shows_help(self, capsys):
        """Test that running without arguments shows help and does nothing."""
        # Running without args should print help and return without error
        call_command("ustaw_daty_oswiadczenia_pbn")

        captured = capsys.readouterr()
        assert "Ustawia datę oświadczenia PBN" in captured.out
        assert "--rok" in captured.out

    def test_wydawnictwo_zwarte_autor_is_also_updated(
        self, wydawnictwo_zwarte, autor_jan_kowalski, jednostka
    ):
        """Test that Wydawnictwo_Zwarte_Autor records are updated."""
        from datetime import date

        wydawnictwo_zwarte.rok = 2024
        wydawnictwo_zwarte.save()

        wza = wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
        wza.data_oswiadczenia = None
        wza.save()

        call_command("ustaw_daty_oswiadczenia_pbn", "--rok", "2024")

        wza.refresh_from_db()
        assert wza.data_oswiadczenia == date(2024, 12, 31)

    def test_nadpisz_overwrites_existing_dates(
        self, wydawnictwo_ciagle, autor_jan_kowalski, jednostka
    ):
        """Test that --nadpisz flag overwrites existing dates."""
        from datetime import date

        wydawnictwo_ciagle.rok = 2024
        wydawnictwo_ciagle.save()

        existing_date = date(2020, 5, 15)
        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = existing_date
        wca.save()

        call_command("ustaw_daty_oswiadczenia_pbn", "--rok", "2024", "--nadpisz")

        wca.refresh_from_db()
        # With --nadpisz, existing date should be overwritten
        assert wca.data_oswiadczenia == date(2024, 12, 31)

    def test_without_nadpisz_skips_existing_dates(
        self, wydawnictwo_ciagle, autor_jan_kowalski, jednostka
    ):
        """Test that without --nadpisz, existing dates are not modified."""
        from datetime import date

        wydawnictwo_ciagle.rok = 2024
        wydawnictwo_ciagle.save()

        existing_date = date(2020, 5, 15)
        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = existing_date
        wca.save()

        call_command("ustaw_daty_oswiadczenia_pbn", "--rok", "2024")

        wca.refresh_from_db()
        # Without --nadpisz, existing date should be preserved
        assert wca.data_oswiadczenia == existing_date
