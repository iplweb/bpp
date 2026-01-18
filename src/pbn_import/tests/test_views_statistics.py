"""Unit tests for PBN import presets views"""

import json

import pytest
from django.test import Client
from django.urls import reverse
from model_bakery import baker

# ============================================================================
# PRESETS VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestImportPresetsView:
    """Test ImportPresetsView"""

    def test_presets_view_requires_permission(self, django_user_model):
        """Test presets view requires permission"""
        client = Client()
        user = baker.make(django_user_model)
        client.force_login(user)

        response = client.get(reverse("pbn_import:presets"))

        assert response.status_code == 403

    def test_presets_view_returns_json(self, django_user_model):
        """Test presets view returns JSON response"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        client.force_login(user)

        response = client.get(reverse("pbn_import:presets"))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert "presets" in data

    def test_presets_view_includes_full_preset(self, django_user_model):
        """Test presets includes 'full' preset"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        client.force_login(user)

        response = client.get(reverse("pbn_import:presets"))

        data = json.loads(response.content)
        preset_ids = [p["id"] for p in data["presets"]]
        assert "full" in preset_ids

    def test_presets_view_includes_update_preset(self, django_user_model):
        """Test presets includes 'update' preset"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        client.force_login(user)

        response = client.get(reverse("pbn_import:presets"))

        data = json.loads(response.content)
        preset_ids = [p["id"] for p in data["presets"]]
        assert "update" in preset_ids
