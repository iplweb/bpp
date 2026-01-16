"""Unit tests for ImportStep model"""

import pytest
from django.db import IntegrityError
from model_bakery import baker

from pbn_import.models import ImportStep

# ============================================================================
# IMPORT STEP MODEL TESTS
# ============================================================================


@pytest.mark.django_db
class TestImportStepModel:
    """Test ImportStep model"""

    def test_import_step_creation(self):
        """Test ImportStep creation with required fields"""
        step = ImportStep.objects.create(
            name="import_authors",
            display_name="Import Authors",
            order=1,
        )

        assert step.name == "import_authors"
        assert step.display_name == "Import Authors"
        assert step.order == 1
        assert step.is_optional is False
        assert step.estimated_duration == 60
        assert step.icon_class == "fi-download"

    def test_import_step_with_optional(self):
        """Test ImportStep with optional field"""
        step = baker.make(
            ImportStep,
            name="optional_step",
            is_optional=True,
        )

        assert step.is_optional is True

    def test_import_step_ordering(self):
        """Test ImportStep objects are ordered by order field"""
        step1 = ImportStep.objects.create(
            name="first",
            display_name="First",
            order=1,
        )
        step2 = ImportStep.objects.create(
            name="second",
            display_name="Second",
            order=2,
        )
        step3 = ImportStep.objects.create(
            name="third",
            display_name="Third",
            order=3,
        )

        steps = list(ImportStep.objects.all())
        assert steps[0] == step1
        assert steps[1] == step2
        assert steps[2] == step3

    def test_import_step_str_representation(self):
        """Test ImportStep __str__ returns display_name"""
        step = baker.make(
            ImportStep,
            display_name="Import Publications",
        )

        assert str(step) == "Import Publications"

    def test_import_step_name_unique(self):
        """Test step name must be unique"""
        ImportStep.objects.create(
            name="unique_step",
            display_name="Display",
            order=1,
        )

        with pytest.raises(IntegrityError):
            ImportStep.objects.create(
                name="unique_step",
                display_name="Different Display",
                order=2,
            )
