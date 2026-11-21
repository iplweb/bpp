"""Motywy front-endu pochodzą z jednej listy w settings (BPP_THEMES).

Patrz docs/superpowers/specs/2026-06-02-motywy-z-settings-design.md
"""

import re
from pathlib import Path

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


# --- Pliki motywów (FD#609: motyw app-apoz) -----------------------------------

REPO = Path(__file__).resolve().parents[4]
SCSS_DIR = REPO / "src" / "bpp" / "static" / "scss"


@pytest.mark.parametrize("value", [value for value, _ in settings.BPP_THEMES])
def test_kazdy_motyw_ma_zrodlo_scss_i_target_grunta(value):
    """Wpis w BPP_THEMES bez pliku SCSS albo targetu w Gruntfile.js daje
    w produkcji 404 na arkusz stylów (strona bez CSS) — pilnujemy obu."""
    assert (SCSS_DIR / f"{value}.scss").is_file()
    gruntfile = (REPO / "Gruntfile.js").read_text(encoding="utf-8")
    assert f"'src/bpp/static/scss/{value}.css'" in gruntfile


def test_motyw_app_apoz_jest_na_liscie():
    assert "app-apoz" in dict(settings.BPP_THEMES)


def test_motyw_app_apoz_fonty_self_hostowane():
    """Inter jest serwowany z naszych plików statycznych — każdy plik
    wskazany w @font-face istnieje, a motyw nie sięga do Google Fonts."""
    src = (SCSS_DIR / "app-apoz.scss").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in src
    assert "fonts.gstatic.com" not in src

    font_dir = REPO / "src" / "bpp" / "static" / "bpp" / "fonts" / "inter"
    wagi = re.search(r"@each \$weight in \(([^)]*)\)", src).group(1)
    wagi = [w.strip() for w in wagi.split(",") if w.strip()]
    assert wagi, "brak listy wag fontu w app-apoz.scss"
    for weight in wagi:
        for subset in ("latin", "latin-ext"):
            plik = font_dir / f"inter-{weight}-{subset}.woff2"
            assert plik.is_file(), plik
