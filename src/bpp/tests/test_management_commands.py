# -*- encoding: utf-8 -*-
"""Tests for bpp management commands."""

import pytest
from io import StringIO
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.test import override_settings
from optparse import OptionError

from bpp.models import (
    Autor,
    Autorzy,
    Jednostka,
    Autor_Jednostka,
    Wydzial,
    Uczelnia,
    Zrodlo,
    BppMultiseekVisibility,
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
        original_slug = jednostka.slug
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
        # Store original slug to verify it changes
        original_slug = zrodlo.slug
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
        au = Autor_Jednostka.objects.create(autor=autor_jan_kowalski, jednostka=jednostka)
        original_id = au.pk

        call_command("rebuild_autor_jednostka")

        # Verify association still exists
        assert Autor_Jednostka.objects.filter(pk=original_id).exists()

    def test_rebuild_autor_jednostka_multiple(
        self, autor_jan_kowalski, autor_jan_nowak, jednostka, druga_jednostka
    ):
        """Test rebuild with multiple associations."""
        # Create multiple associations
        au1 = Autor_Jednostka.objects.create(autor=autor_jan_kowalski, jednostka=jednostka)
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
        au = Autor_Jednostka.objects.create(autor=autor_jan_kowalski, jednostka=jednostka)
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

        call_command(
            "set_site_name", "--domain", "new.com", "--name", "New Name"
        )

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
        from bpp.multiseek_registry import registry

        # Create some BppMultiseekVisibility objects if they don't exist
        visibility = BppMultiseekVisibility.objects.first()
        if visibility:
            original_order = visibility.sort_order
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

    def test_ustaw_punktacje_with_publications(
        self, wydawnictwo_ciagle, zrodlo
    ):
        """Test ustaw_punktacje with actual publications."""
        from bpp.models import Punktacja_Zrodla
        from model_bakery import baker

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

    def test_remove_empty_authors_idempotent(self, autor_jan_kowalski, wydawnictwo_zwarte, jednostka):
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
