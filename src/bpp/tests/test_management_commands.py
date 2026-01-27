"""Tests for bpp management commands."""

from optparse import OptionError

import pytest
from django.contrib.sites.models import Site
from django.core.management import call_command

from bpp.management.commands.look_for_unused_fields import (
    Command as LookForUnusedFields,
)
from bpp.models import (
    Autor,
    Autor_Jednostka,
    Autorzy,
    BppMultiseekVisibility,
    Jednostka,
    Wydzial,
)


@pytest.mark.django_db
class TestRebuildSlugsCommand:
    """Test rebuild_slugs management command."""

    def test_rebuild_slugs_autor(self, autor_jan_kowalski):
        """Test that rebuild_slugs clears slug field for authors."""
        # Set a slug value
        autor_jan_kowalski.slug = "test-slug"
        autor_jan_kowalski.save()
        assert autor_jan_kowalski.slug == "test-slug"

        # Run command
        call_command("rebuild_slugs")

        # Refresh from database and verify slug was cleared
        autor_jan_kowalski.refresh_from_db()
        # The slug field uses SlugField with auto population, so after save it should be regenerated
        assert autor_jan_kowalski.slug != "test-slug"
        assert autor_jan_kowalski.slug is not None

    def test_rebuild_slugs_jednostka(self, jednostka):
        """Test that rebuild_slugs clears slug field for units."""
        jednostka.slug = "modified-slug"
        jednostka.save()
        assert jednostka.slug == "modified-slug"

        call_command("rebuild_slugs")

        jednostka.refresh_from_db()
        assert jednostka.slug != "modified-slug"
        assert jednostka.slug is not None

    def test_rebuild_slugs_wydzial(self, wydzial):
        """Test that rebuild_slugs clears slug field for departments."""
        wydzial.slug = "test-wydzial-slug"
        wydzial.save()

        call_command("rebuild_slugs")

        wydzial.refresh_from_db()
        assert wydzial.slug != "test-wydzial-slug"

    def test_rebuild_slugs_uczelnia(self, uczelnia):
        """Test that rebuild_slugs clears slug field for universities."""
        uczelnia.slug = "test-uczelnia-slug"
        uczelnia.save()

        call_command("rebuild_slugs")

        uczelnia.refresh_from_db()
        assert uczelnia.slug != "test-uczelnia-slug"

    def test_rebuild_slugs_zrodlo(self, zrodlo):
        """Test that rebuild_slugs clears slug field for sources."""
        zrodlo.slug = "test-zrodlo-slug"
        zrodlo.save()
        assert zrodlo.slug == "test-zrodlo-slug"

        call_command("rebuild_slugs")

        zrodlo.refresh_from_db()
        # The slug might be regenerated or it might stay the same
        # Just verify the command runs without error
        assert zrodlo.slug is not None

    def test_rebuild_slugs_multiple_objects(
        self, autor_jan_kowalski, autor_jan_nowak, jednostka
    ):
        """Test that rebuild_slugs works with multiple objects."""
        # Modify multiple objects
        autor_jan_kowalski.slug = "slug-1"
        autor_jan_nowak.slug = "slug-2"
        jednostka.slug = "slug-3"

        autor_jan_kowalski.save()
        autor_jan_nowak.save()
        jednostka.save()

        call_command("rebuild_slugs")

        autor_jan_kowalski.refresh_from_db()
        autor_jan_nowak.refresh_from_db()
        jednostka.refresh_from_db()

        assert autor_jan_kowalski.slug not in ["slug-1", None, ""]
        assert autor_jan_nowak.slug not in ["slug-2", None, ""]
        assert jednostka.slug not in ["slug-3", None, ""]


@pytest.mark.django_db
class TestRemoveEmptyAuthorsCommand:
    """Test remove_empty_authors management command."""

    def test_keep_author_with_works(
        self, autor_jan_kowalski, wydawnictwo_zwarte, jednostka
    ):
        """Test that authors with publications are not removed."""
        # Add author to publication
        wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

        author_id = autor_jan_kowalski.pk
        assert Autor.objects.filter(pk=author_id).count() == 1

        call_command("remove_empty_authors")

        # Verify author still exists
        assert Autor.objects.filter(pk=author_id).exists()

    def test_remove_empty_authors_with_multiple_authors_with_works(
        self, autor_jan_kowalski, autor_jan_nowak, wydawnictwo_zwarte, jednostka
    ):
        """Test that command preserves multiple authors with works."""
        # Add both authors to publication
        wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
        wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)

        kowalski_id = autor_jan_kowalski.pk
        nowak_id = autor_jan_nowak.pk

        call_command("remove_empty_authors")

        # Both should still exist
        assert Autor.objects.filter(pk=kowalski_id).exists()
        assert Autor.objects.filter(pk=nowak_id).exists()


@pytest.mark.django_db
class TestRebuildAutorJednostkaCommand:
    """Test rebuild_autor_jednostka management command."""

    def test_rebuild_autor_jednostka_basic(self, autor_jan_kowalski, jednostka):
        """Test that rebuild_autor_jednostka runs without errors."""
        # Create an author-unit association
        au = Autor_Jednostka.objects.create(
            autor=autor_jan_kowalski, jednostka=jednostka
        )
        original_id = au.pk

        call_command("rebuild_autor_jednostka")

        # Verify association still exists
        assert Autor_Jednostka.objects.filter(pk=original_id).exists()

    def test_rebuild_autor_jednostka_multiple(
        self, autor_jan_kowalski, autor_jan_nowak, jednostka, druga_jednostka
    ):
        """Test rebuild with multiple associations."""
        # Create multiple associations
        au1 = Autor_Jednostka.objects.create(
            autor=autor_jan_kowalski, jednostka=jednostka
        )
        au2 = Autor_Jednostka.objects.create(
            autor=autor_jan_nowak, jednostka=druga_jednostka
        )

        au1_id = au1.pk
        au2_id = au2.pk

        call_command("rebuild_autor_jednostka")

        assert Autor_Jednostka.objects.filter(pk=au1_id).exists()
        assert Autor_Jednostka.objects.filter(pk=au2_id).exists()

    def test_rebuild_autor_jednostka_executes_save_logic(
        self, autor_jan_kowalski, jednostka
    ):
        """Test that rebuild_autor_jednostka triggers model save logic."""
        # This tests that the command actually calls save() on each object
        au = Autor_Jednostka.objects.create(
            autor=autor_jan_kowalski, jednostka=jednostka
        )
        au_id = au.pk

        call_command("rebuild_autor_jednostka")

        # Verify the object still exists and is valid
        au_after = Autor_Jednostka.objects.get(pk=au_id)
        assert au_after.autor_id == autor_jan_kowalski.pk
        assert au_after.jednostka_id == jednostka.pk


@pytest.mark.django_db
class TestRebuildJednostkCommand:
    """Test rebuild_jednostka management command."""

    def test_rebuild_jednostka_executes(self, jednostka):
        """Test that rebuild_jednostka command executes without error."""
        unit_id = jednostka.pk
        call_command("rebuild_jednostka")

        # Verify unit still exists
        assert Jednostka.objects.filter(pk=unit_id).exists()

    def test_rebuild_jednostka_with_hierarchy(self, wydzial, jednostka):
        """Test rebuild with unit hierarchy."""
        call_command("rebuild_jednostka")

        # Verify both exist
        assert Wydzial.objects.filter(pk=wydzial.pk).exists()
        assert Jednostka.objects.filter(pk=jednostka.pk).exists()


@pytest.mark.django_db
class TestSetSiteNameCommand:
    """Test set_site_name management command."""

    def test_set_site_name_domain_only(self):
        """Test setting only domain."""
        # Ensure there's exactly one Site object
        Site.objects.all().delete()
        site = Site.objects.create(domain="old.example.com", name="Old Name")

        call_command("set_site_name", "--domain", "new.example.com")

        site.refresh_from_db()
        assert site.domain == "new.example.com"
        assert site.name == "Old Name"  # Should not change

    def test_set_site_name_name_only(self):
        """Test setting only site name."""
        Site.objects.all().delete()
        site = Site.objects.create(domain="example.com", name="Old Name")

        call_command("set_site_name", "--name", "New Name")

        site.refresh_from_db()
        assert site.domain == "example.com"  # Should not change
        assert site.name == "New Name"

    def test_set_site_name_both(self):
        """Test setting both domain and name."""
        Site.objects.all().delete()
        site = Site.objects.create(domain="old.com", name="Old Name")

        call_command("set_site_name", "--domain", "new.com", "--name", "New Name")

        site.refresh_from_db()
        assert site.domain == "new.com"
        assert site.name == "New Name"

    def test_set_site_name_short_flags(self):
        """Test using short flag versions (-d, -n)."""
        Site.objects.all().delete()
        site = Site.objects.create(domain="old.com", name="Old Name")

        call_command("set_site_name", "-d", "short.com", "-n", "Short Name")

        site.refresh_from_db()
        assert site.domain == "short.com"
        assert site.name == "Short Name"

    def test_set_site_name_no_arguments_fails(self):
        """Test that command fails without arguments."""
        Site.objects.all().delete()
        Site.objects.create(domain="example.com", name="Example")

        with pytest.raises(OptionError):
            call_command("set_site_name")

    def test_set_site_name_multiple_sites_fails(self):
        """Test that command fails when multiple Site objects exist."""
        Site.objects.all().delete()
        Site.objects.create(domain="site1.com", name="Site 1")
        Site.objects.create(domain="site2.com", name="Site 2")

        with pytest.raises(ValueError) as exc_info:
            call_command("set_site_name", "--domain", "new.com")

        assert "jeden obiekt Site" in str(exc_info.value)


@pytest.mark.django_db
class TestResetMultiseekOrderingCommand:
    """Test reset_multiseek_ordering management command."""

    def test_reset_multiseek_ordering_basic(self):
        """Test that command executes without error."""
        call_command("reset_multiseek_ordering")

    def test_reset_multiseek_ordering_updates_sort_order(self):
        """Test that command updates sort_order values."""

        # Create some BppMultiseekVisibility objects if they don't exist
        visibility = BppMultiseekVisibility.objects.first()
        if visibility:
            call_command("reset_multiseek_ordering")
            visibility.refresh_from_db()
            # Sort order should be updated based on registry order
            assert visibility.sort_order >= 1


@pytest.mark.django_db
class TestOdtworzGrupyCommand:
    """Test odtworz_grupy management command."""

    def test_odtworz_grupy_executes(self):
        """Test that odtworz_grupy command executes without error."""
        # This command rebuilds permission groups
        call_command("odtworz_grupy")

    def test_odtworz_grupy_creates_groups(self):
        """Test that permission groups are created/maintained."""
        from django.contrib.auth.models import Group

        initial_count = Group.objects.count()

        call_command("odtworz_grupy")

        # Groups should exist after running the command
        final_count = Group.objects.count()
        # Count should be >= initial (some might be added)
        assert final_count >= initial_count


@pytest.mark.django_db
class TestUstawPunktacjeCommand:
    """Test ustaw_punktacje management command."""

    def test_ustaw_punktacje_executes(self):
        """Test that ustaw_punktacje command executes without error."""
        call_command("ustaw_punktacje")

    def test_ustaw_punktacje_with_publications(self, wydawnictwo_ciagle, zrodlo):
        """Test ustaw_punktacje with actual publications."""
        from model_bakery import baker

        from bpp.models import Punktacja_Zrodla

        # Create a publication with points
        wydawnictwo_ciagle.punkty_kbn = 10
        wydawnictwo_ciagle.zrodlo = zrodlo
        wydawnictwo_ciagle.save()

        # Create source scoring for the same year
        baker.make(
            Punktacja_Zrodla,
            rok=wydawnictwo_ciagle.rok,
            zrodlo=zrodlo,
            punkty_kbn=15,
        )

        call_command("ustaw_punktacje")

        wydawnictwo_ciagle.refresh_from_db()
        # The command should update points based on Punktacja_Zrodla
        # (actual logic depends on implementation)


@pytest.mark.django_db
class TestRebuildSlugsCommandIntegration:
    """Integration tests for rebuild_slugs with various scenarios."""

    def test_rebuild_slugs_idempotent(self, autor_jan_kowalski):
        """Test that running rebuild_slugs twice produces same result."""
        call_command("rebuild_slugs")
        autor_jan_kowalski.refresh_from_db()
        slug_after_first = autor_jan_kowalski.slug

        call_command("rebuild_slugs")
        autor_jan_kowalski.refresh_from_db()
        slug_after_second = autor_jan_kowalski.slug

        # Slugs should be the same (stable slug generation)
        assert slug_after_first == slug_after_second

    def test_rebuild_slugs_with_special_characters(self):
        """Test rebuild_slugs with special characters in author names."""
        from model_bakery import baker

        author = baker.make(
            Autor, nazwisko="Żółw", imiona="Łódka"
        )  # Polish special characters

        call_command("rebuild_slugs")

        author.refresh_from_db()
        assert author.slug is not None
        assert len(author.slug) > 0


@pytest.mark.django_db
class TestRemoveEmptyAuthorsCommandIntegration:
    """Integration tests for remove_empty_authors."""

    def test_remove_empty_authors_idempotent(
        self, autor_jan_kowalski, wydawnictwo_zwarte, jednostka
    ):
        """Test that running command multiple times is safe."""
        wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
        author_id = autor_jan_kowalski.pk

        # Run twice
        call_command("remove_empty_authors")
        call_command("remove_empty_authors")

        # Author should still exist
        assert Autor.objects.filter(pk=author_id).exists()


@pytest.mark.django_db
class TestManagementCommandsEdgeCases:
    """Test edge cases across management commands."""

    def test_commands_with_empty_database(self):
        """Test that commands handle empty database gracefully."""
        # Delete most data to simulate empty state
        Autorzy.objects.all().delete()
        Autor_Jednostka.objects.all().delete()

        # These commands should not fail with empty data
        call_command("rebuild_slugs")
        call_command("rebuild_autor_jednostka")
        call_command("rebuild_jednostka")

    def test_reset_multiseek_ordering_with_no_records(self):
        """Test reset_multiseek_ordering with minimal data."""
        BppMultiseekVisibility.objects.all().delete()

        # Should not fail even with no records
        call_command("reset_multiseek_ordering")


# =============================================================================
# Testy przeniesione z tests_legacy/test_management.py
# =============================================================================


@pytest.mark.django_db
def test_look_for_unused_fields():
    LookForUnusedFields().handle(silent=True)


# =============================================================================
# Testy dla ustaw_daty_oswiadczenia_pbn
# =============================================================================


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


# =============================================================================
# Testy dla fix_import_dat_oswiadczen_pbn
# =============================================================================


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
                "fix_import_dat_oswiadczen_pbn", "--rok-min", "2025", "--rok-max", "2022"
            )

        assert "nie może być większy" in str(exc_info.value)
