"""Tests for the ``fix_import_dat_oswiadczen_pbn`` management command.

Wydzielone z ``test_management_commands.py``, by trzymać per-komendę
spójne grupy testów w plikach <850 linii.
"""

import pytest
from django.core.management import call_command


@pytest.mark.django_db
class TestFixImportDatOswiadczenPbnCommand:
    """Test fix_import_dat_oswiadczen_pbn management command."""

    def test_basic_import_copies_stated_timestamp(
        self,
        wydawnictwo_ciagle,
        autor_jan_kowalski,
        jednostka,
    ):
        """Test basic import copies statedTimestamp to data_oswiadczenia."""
        from datetime import date
        from uuid import uuid4

        from model_bakery import baker

        from pbn_api.models import (
            Institution,
            OswiadczenieInstytucji,
            Publication,
            Scientist,
        )

        # Create PBN Publication and link to wydawnictwo_ciagle
        pbn_publication = baker.make(Publication)
        wydawnictwo_ciagle.rok = 2024
        wydawnictwo_ciagle.pbn_uid = pbn_publication
        wydawnictwo_ciagle.save()

        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = None
        wca.save()

        # Create PBN Scientist linked to autor
        pbn_scientist = baker.make(Scientist)
        autor_jan_kowalski.pbn_uid = pbn_scientist
        autor_jan_kowalski.save()

        # Create Institution for OswiadczenieInstytucji
        pbn_institution = baker.make(Institution)

        # Create OswiadczenieInstytucji with statedTimestamp
        stated_date = date(2024, 6, 15)
        baker.make(
            OswiadczenieInstytucji,
            id=uuid4(),
            publicationId=pbn_publication,
            personId=pbn_scientist,
            institutionId=pbn_institution,
            statedTimestamp=stated_date,
            addedTimestamp=date(2024, 1, 1),
            inOrcid=False,
            type="AUTHOR",
        )

        call_command("fix_import_dat_oswiadczen_pbn")

        wca.refresh_from_db()
        assert wca.data_oswiadczenia == stated_date

    def test_nadpisz_overwrites_existing_dates(
        self,
        wydawnictwo_ciagle,
        autor_jan_kowalski,
        jednostka,
    ):
        """Test that --nadpisz flag overwrites existing dates."""
        from datetime import date
        from uuid import uuid4

        from model_bakery import baker

        from pbn_api.models import (
            Institution,
            OswiadczenieInstytucji,
            Publication,
            Scientist,
        )

        pbn_publication = baker.make(Publication)
        wydawnictwo_ciagle.rok = 2024
        wydawnictwo_ciagle.pbn_uid = pbn_publication
        wydawnictwo_ciagle.save()

        existing_date = date(2020, 5, 15)
        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = existing_date
        wca.save()

        pbn_scientist = baker.make(Scientist)
        autor_jan_kowalski.pbn_uid = pbn_scientist
        autor_jan_kowalski.save()

        pbn_institution = baker.make(Institution)

        new_stated_date = date(2024, 7, 20)
        baker.make(
            OswiadczenieInstytucji,
            id=uuid4(),
            publicationId=pbn_publication,
            personId=pbn_scientist,
            institutionId=pbn_institution,
            statedTimestamp=new_stated_date,
            addedTimestamp=date(2024, 1, 1),
            inOrcid=False,
            type="AUTHOR",
        )

        call_command("fix_import_dat_oswiadczen_pbn", "--nadpisz")

        wca.refresh_from_db()
        assert wca.data_oswiadczenia == new_stated_date

    def test_without_nadpisz_skips_existing_dates(
        self,
        wydawnictwo_ciagle,
        autor_jan_kowalski,
        jednostka,
    ):
        """Test that without --nadpisz, existing dates are not modified."""
        from datetime import date
        from uuid import uuid4

        from model_bakery import baker

        from pbn_api.models import (
            Institution,
            OswiadczenieInstytucji,
            Publication,
            Scientist,
        )

        pbn_publication = baker.make(Publication)
        wydawnictwo_ciagle.rok = 2024
        wydawnictwo_ciagle.pbn_uid = pbn_publication
        wydawnictwo_ciagle.save()

        existing_date = date(2020, 5, 15)
        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = existing_date
        wca.save()

        pbn_scientist = baker.make(Scientist)
        autor_jan_kowalski.pbn_uid = pbn_scientist
        autor_jan_kowalski.save()

        pbn_institution = baker.make(Institution)

        new_stated_date = date(2024, 7, 20)
        baker.make(
            OswiadczenieInstytucji,
            id=uuid4(),
            publicationId=pbn_publication,
            personId=pbn_scientist,
            institutionId=pbn_institution,
            statedTimestamp=new_stated_date,
            addedTimestamp=date(2024, 1, 1),
            inOrcid=False,
            type="AUTHOR",
        )

        call_command("fix_import_dat_oswiadczen_pbn")

        wca.refresh_from_db()
        # Without --nadpisz, existing date should be preserved
        assert wca.data_oswiadczenia == existing_date

    def test_year_filter_with_rok(
        self,
        wydawnictwo_ciagle,
        wydawnictwo_zwarte,
        autor_jan_kowalski,
        jednostka,
    ):
        """Test filtering by single year with --rok."""
        from datetime import date
        from uuid import uuid4

        from model_bakery import baker

        from pbn_api.models import (
            Institution,
            OswiadczenieInstytucji,
            Publication,
            Scientist,
        )

        # Setup wydawnictwo_ciagle for 2024
        pbn_pub_ciagle = baker.make(Publication)
        wydawnictwo_ciagle.rok = 2024
        wydawnictwo_ciagle.pbn_uid = pbn_pub_ciagle
        wydawnictwo_ciagle.save()
        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = None
        wca.save()

        # Setup wydawnictwo_zwarte for 2023
        pbn_pub_zwarte = baker.make(Publication)
        wydawnictwo_zwarte.rok = 2023
        wydawnictwo_zwarte.pbn_uid = pbn_pub_zwarte
        wydawnictwo_zwarte.save()
        wza = wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
        wza.data_oswiadczenia = None
        wza.save()

        pbn_scientist = baker.make(Scientist)
        autor_jan_kowalski.pbn_uid = pbn_scientist
        autor_jan_kowalski.save()

        pbn_institution = baker.make(Institution)

        stated_date_2024 = date(2024, 6, 15)
        stated_date_2023 = date(2023, 6, 15)

        baker.make(
            OswiadczenieInstytucji,
            id=uuid4(),
            publicationId=pbn_pub_ciagle,
            personId=pbn_scientist,
            institutionId=pbn_institution,
            statedTimestamp=stated_date_2024,
            addedTimestamp=date(2024, 1, 1),
            inOrcid=False,
            type="AUTHOR",
        )
        baker.make(
            OswiadczenieInstytucji,
            id=uuid4(),
            publicationId=pbn_pub_zwarte,
            personId=pbn_scientist,
            institutionId=pbn_institution,
            statedTimestamp=stated_date_2023,
            addedTimestamp=date(2023, 1, 1),
            inOrcid=False,
            type="AUTHOR",
        )

        # Filter only 2024
        call_command("fix_import_dat_oswiadczen_pbn", "--rok", "2024")

        wca.refresh_from_db()
        wza.refresh_from_db()

        # 2024 should be updated
        assert wca.data_oswiadczenia == stated_date_2024
        # 2023 should remain None (filtered out)
        assert wza.data_oswiadczenia is None

    def test_dry_run_does_not_modify_data(
        self,
        wydawnictwo_ciagle,
        autor_jan_kowalski,
        jednostka,
    ):
        """Test that dry-run mode does not save changes."""
        from datetime import date
        from uuid import uuid4

        from django.db import transaction
        from model_bakery import baker

        from pbn_api.models import (
            Institution,
            OswiadczenieInstytucji,
            Publication,
            Scientist,
        )

        pbn_publication = baker.make(Publication)
        wydawnictwo_ciagle.rok = 2024
        wydawnictwo_ciagle.pbn_uid = pbn_publication
        wydawnictwo_ciagle.save()

        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = None
        wca.save()

        pbn_scientist = baker.make(Scientist)
        autor_jan_kowalski.pbn_uid = pbn_scientist
        autor_jan_kowalski.save()

        pbn_institution = baker.make(Institution)

        stated_date = date(2024, 6, 15)
        baker.make(
            OswiadczenieInstytucji,
            id=uuid4(),
            publicationId=pbn_publication,
            personId=pbn_scientist,
            institutionId=pbn_institution,
            statedTimestamp=stated_date,
            addedTimestamp=date(2024, 1, 1),
            inOrcid=False,
            type="AUTHOR",
        )

        # Dry run raises TransactionManagementError to roll back
        with pytest.raises(transaction.TransactionManagementError):
            call_command("fix_import_dat_oswiadczen_pbn", "--dry-run")

        wca.refresh_from_db()
        assert wca.data_oswiadczenia is None

    def test_skips_records_without_stated_timestamp(
        self,
        wydawnictwo_ciagle,
        autor_jan_kowalski,
        jednostka,
    ):
        """Test that records with NULL statedTimestamp are properly skipped."""
        from datetime import date
        from uuid import uuid4

        from model_bakery import baker

        from pbn_api.models import (
            Institution,
            OswiadczenieInstytucji,
            Publication,
            Scientist,
        )

        pbn_publication = baker.make(Publication)
        wydawnictwo_ciagle.rok = 2024
        wydawnictwo_ciagle.pbn_uid = pbn_publication
        wydawnictwo_ciagle.save()

        wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
        wca.data_oswiadczenia = None
        wca.save()

        pbn_scientist = baker.make(Scientist)
        autor_jan_kowalski.pbn_uid = pbn_scientist
        autor_jan_kowalski.save()

        pbn_institution = baker.make(Institution)

        # Create OswiadczenieInstytucji WITHOUT statedTimestamp (NULL)
        baker.make(
            OswiadczenieInstytucji,
            id=uuid4(),
            publicationId=pbn_publication,
            personId=pbn_scientist,
            institutionId=pbn_institution,
            statedTimestamp=None,  # NULL - should be skipped
            addedTimestamp=date(2024, 1, 1),
            inOrcid=False,
            type="AUTHOR",
        )

        call_command("fix_import_dat_oswiadczen_pbn")

        wca.refresh_from_db()
        # Should remain None because the only OswiadczenieInstytucji
        # has NULL statedTimestamp
        assert wca.data_oswiadczenia is None

    def test_rok_with_rok_min_fails(self):
        """Test that using --rok with --rok-min raises error."""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError) as exc_info:
            call_command(
                "fix_import_dat_oswiadczen_pbn", "--rok", "2024", "--rok-min", "2022"
            )

        assert "Nie można używać --rok razem z --rok-min/--rok-max" in str(
            exc_info.value
        )

    def test_rok_min_without_rok_max_fails(self):
        """Test that using --rok-min without --rok-max raises error."""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError) as exc_info:
            call_command("fix_import_dat_oswiadczen_pbn", "--rok-min", "2022")

        assert "muszą być używane razem" in str(exc_info.value)

    def test_rok_max_without_rok_min_fails(self):
        """Test that using --rok-max without --rok-min raises error."""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError) as exc_info:
            call_command("fix_import_dat_oswiadczen_pbn", "--rok-max", "2025")

        assert "muszą być używane razem" in str(exc_info.value)

    def test_rok_min_greater_than_rok_max_fails(self):
        """Test that --rok-min > --rok-max raises error."""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError) as exc_info:
            call_command(
                "fix_import_dat_oswiadczen_pbn",
                "--rok-min",
                "2025",
                "--rok-max",
                "2022",
            )

        assert "nie może być większy" in str(exc_info.value)
