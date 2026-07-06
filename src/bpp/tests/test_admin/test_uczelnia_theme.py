"""Motywy front-endu pochodzą z jednej listy w settings (BPP_THEMES).

Patrz docs/superpowers/specs/2026-06-02-motywy-z-settings-design.md
"""

import pytest
from django.conf import settings

from bpp.models import Uczelnia


def test_theme_name_field_ma_choices_z_settings():
    """Model nie zamraża listy motywów (zero migracji przy zmianie listy).

    Pole `theme_name` to zwykły CharField — dozwolone wartości żyją w
    settings.BPP_THEMES, a nie w `choices` pola modelu.
    """
    field = Uczelnia._meta.get_field("theme_name")
    assert not field.choices, (
        "theme_name nie powinno mieć statycznych choices na poziomie modelu "
        "— inaczej każda zmiana listy motywów wymusza migrację."
    )


def test_bpp_themes_jest_lista_wartosc_etykieta():
    """settings.BPP_THEMES to lista krotek (wartość, etykieta)."""
    assert settings.BPP_THEMES
    for entry in settings.BPP_THEMES:
        value, label = entry  # rozpakowanie wymusza kształt 2-krotki
        assert value and label


def test_compress_offline_context_wyliczany_z_bpp_themes():
    """COMPRESS_OFFLINE_CONTEXT pochodzi z BPP_THEMES (bez drugiej listy)."""
    ctx = settings.COMPRESS_OFFLINE_CONTEXT
    assert len(ctx) == len(settings.BPP_THEMES)
    expected = {f"scss/{value}.css" for value, _ in settings.BPP_THEMES}
    assert {c["THEME_NAME"] for c in ctx} == expected


@pytest.mark.django_db
def test_admin_form_oferuje_motywy_z_settings():
    """Dropdown w adminie uczelni odbija aktualną listę z settings."""
    from bpp.admin.uczelnia import UczelniaAdminForm

    form = UczelniaAdminForm()
    assert list(form.fields["theme_name"].choices) == list(settings.BPP_THEMES)
