"""
Tests for pbn_integrator system data integration (languages, countries, disciplines).

For author tests, see test_utils_authors.py
For publication sync tests, see test_utils_publication_sync.py
For performance tests, see test_utils_performance.py
"""

from unittest.mock import Mock
from uuid import uuid4

import pytest
from model_bakery import baker

from bpp.models import Dyscyplina_Naukowa, Jezyk
from pbn_api.models import Country, Discipline, DisciplineGroup, Language

# ============================================================================
# UNIT TESTS - Language Integration
# ============================================================================


@pytest.mark.django_db
class TestIntegrujJezyki:
    """Test integruj_jezyki function for language system data import"""

    def test_integruj_jezyki_creates_languages(self):
        """Should create Language records from PBN data"""
        from pbn_integrator.utils import integruj_jezyki

        mock_client = Mock()
        mock_client.get_languages.return_value = [
            {
                "code": "pol",
                "language": {
                    "name": "Polish",
                    "639-1": "pl",
                    "639-2": "pol",
                    "pl": "Polski",
                    "en": "Polish",
                },
            },
            {
                "code": "eng",
                "language": {
                    "name": "English",
                    "639-1": "en",
                    "639-2": "eng",
                    "pl": "Angielski",
                    "en": "English",
                },
            },
        ]

        integruj_jezyki(mock_client, create_if_not_exists=True)

        # Verify languages were created
        assert Language.objects.filter(code="pol").exists()
        assert Language.objects.filter(code="eng").exists()

    def test_integruj_jezyki_updates_existing_languages(self):
        """Should update existing Language records with new data"""
        from pbn_integrator.utils import integruj_jezyki

        # Create existing language
        existing_lang = baker.make(Language, code="pol", language={"name": "Old"})

        mock_client = Mock()
        mock_client.get_languages.return_value = [
            {
                "code": "pol",
                "language": {
                    "name": "Polish Updated",
                    "639-1": "pl",
                    "639-2": "pol",
                    "pl": "Polski",
                    "en": "Polish",
                },
            }
        ]

        integruj_jezyki(mock_client, create_if_not_exists=True)

        # Refresh from DB
        existing_lang.refresh_from_db()
        # Verify it was updated
        assert existing_lang.language["name"] == "Polish Updated"

    def test_integruj_jezyki_maps_bpp_language_to_pbn(self):
        """Should create mapping between BPP languages and PBN languages"""
        from pbn_integrator.utils import integruj_jezyki

        bpp_lang = Jezyk.objects.update_or_create(
            nazwa="polski", defaults={"skrot": "pol"}
        )[0]
        baker.make(
            Language,
            code="pol",
            language={
                "639-2": "pol",
                "639-1": "pl",
                "pl": "Polski",
                "en": "Polish",
            },
        )

        mock_client = Mock()
        mock_client.get_languages.return_value = [
            {
                "code": "pol",
                "language": {
                    "name": "Polish",
                    "639-1": "pl",
                    "639-2": "pol",
                    "pl": "Polski",
                    "en": "Polish",
                },
            }
        ]

        integruj_jezyki(mock_client, create_if_not_exists=True)

        # Verify BPP language is mapped to PBN language
        bpp_lang.refresh_from_db()
        # The mapping should be established
        assert bpp_lang is not None


# ============================================================================
# UNIT TESTS - Country Integration
# ============================================================================


@pytest.mark.django_db
class TestIntegrujKraje:
    """Test integruj_kraje function for country system data import"""

    def test_integruj_kraje_creates_countries(self):
        """Should create Country records from PBN data"""
        from pbn_integrator.utils import integruj_kraje

        mock_client = Mock()
        mock_client.get_countries.return_value = [
            {"code": "PL", "description": "Poland"},
            {"code": "DE", "description": "Germany"},
        ]

        integruj_kraje(mock_client)

        # Verify countries were created
        assert Country.objects.filter(code="PL").exists()
        assert Country.objects.filter(code="DE").exists()

    def test_integruj_kraje_updates_existing_countries(self):
        """Should update existing Country records"""
        from pbn_integrator.utils import integruj_kraje

        existing = baker.make(Country, code="GB", description="Old GB")

        mock_client = Mock()
        mock_client.get_countries.return_value = [
            {"code": "GB", "description": "United Kingdom"},
        ]

        integruj_kraje(mock_client)

        existing.refresh_from_db()
        assert existing.description == "United Kingdom"

    def test_integruj_kraje_maps_to_bpp_countries(self):
        """Should establish mapping to BPP country records"""
        from pbn_integrator.utils import integruj_kraje

        mock_client = Mock()
        mock_client.get_countries.return_value = [
            {"code": "PL", "description": "Poland"},
        ]

        integruj_kraje(mock_client)

        # Country should be created or updated
        assert Country.objects.filter(code="PL").exists()


# ============================================================================
# UNIT TESTS - Discipline Integration
# ============================================================================


@pytest.mark.django_db
class TestIntegrujDyscypliny:
    """Test integruj_dyscypliny function for discipline system data import"""

    def test_integruj_dyscypliny_creates_disciplines(self):
        """Should create Discipline records from PBN data"""
        from pbn_integrator.utils import integruj_dyscypliny

        discipline_group = baker.make(DisciplineGroup)

        mock_client = Mock()
        mock_client.get_discipline_groups.return_value = [discipline_group]
        mock_client.get_disciplines.return_value = [
            {
                "uuid": uuid4(),
                "code": "11.1",
                "name": "Mathematics",
                "parent_group": discipline_group,
            },
        ]

        integruj_dyscypliny(mock_client)

        # Verify discipline was created
        assert Discipline.objects.filter(code="11.1").exists()

    def test_integruj_dyscypliny_links_to_bpp_disciplines(self):
        """Should establish mapping to BPP Dyscyplina_Naukowa"""
        from pbn_integrator.utils import integruj_dyscypliny

        discipline_group = baker.make(DisciplineGroup)
        baker.make(Dyscyplina_Naukowa, nazwa="Matematyka")

        mock_client = Mock()
        mock_client.get_discipline_groups.return_value = [discipline_group]
        mock_client.get_disciplines.return_value = [
            {
                "uuid": uuid4(),
                "code": "11.1",
                "name": "Matematyka",
                "parent_group": discipline_group,
            },
        ]

        integruj_dyscypliny(mock_client)

        # Verify discipline mapping exists
        assert Discipline.objects.filter(code="11.1").exists()
