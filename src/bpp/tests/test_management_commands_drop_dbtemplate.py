"""Testy komendy ``drop_dbtemplate``.

Komenda usuwa wiersz dbtemplate z bazy (żeby renderowanie spadło na zawsze
aktualny plik z dysku), radząc sobie z FK ``PROTECT`` od
``SzablonDlaOpisuBibliograficznego``, a następnie wymusza przebudowę
denormalizowanego ``opis_bibliograficzny_cache`` z dysku.
"""

import pytest
from dbtemplates.models import Template
from denorm import denorms
from django.core.management import call_command

from bpp.dbtemplates_sync import wyczysc_cache_dbtemplate
from bpp.models import Wydawnictwo_Zwarte
from bpp.models.szablondlaopisubibliograficznego import (
    SzablonDlaOpisuBibliograficznego,
)
from bpp.util import rebuild_instances_of_models
from pbn_api.models import Publication


@pytest.mark.django_db
def test_drop_dbtemplate_usuwa_wiersz_i_chroniacy_szablon():
    """Usuwa Template oraz PROTECT-ujący go Szablon(model=None)."""
    tpl, _ = Template.objects.get_or_create(
        name="opis_bibliograficzny.html", defaults={"content": "stara treść"}
    )
    SzablonDlaOpisuBibliograficznego.objects.get_or_create(
        model=None, defaults={"template": tpl}
    )
    assert SzablonDlaOpisuBibliograficznego.objects.filter(
        template__name="opis_bibliograficzny.html"
    ).exists()

    call_command("drop_dbtemplate", "opis_bibliograficzny.html", "--skip-rebuild")

    assert not Template.objects.filter(name="opis_bibliograficzny.html").exists()
    assert not SzablonDlaOpisuBibliograficznego.objects.filter(
        template__name="opis_bibliograficzny.html"
    ).exists()


@pytest.mark.django_db
def test_drop_dbtemplate_idempotentne_gdy_brak_wiersza():
    """Brak wiersza w bazie -> komenda nie wywala się (no-op + ostrzeżenie)."""
    Template.objects.filter(name="nieistnieje.html").delete()
    call_command("drop_dbtemplate", "nieistnieje.html", "--skip-rebuild")


@pytest.mark.django_db
def test_drop_dbtemplate_przebudowuje_cache_z_dysku(wydawnictwo_zwarte):
    """Stary dbtemplate w bazie zasłania dysk -> opis_bibliograficzny_cache jest
    stary. Po drop_dbtemplate render spada na dysk i cache się przebudowuje."""
    pbn_pub = Publication.objects.create(
        mongoId="drop-cmd-rozdzial",
        versions=[{"current": True, "object": {"book": {"title": "Rodzic Z Dysku"}}}],
    )
    wydawnictwo_zwarte.pbn_uid = pbn_pub
    wydawnictwo_zwarte.wydawnictwo_nadrzedne = None
    wydawnictwo_zwarte.wydawnictwo_nadrzedne_w_pbn = None
    wydawnictwo_zwarte.informacje = ""
    wydawnictwo_zwarte.zrodlo = None
    wydawnictwo_zwarte.save()

    # Stary dbtemplate w bazie zasłaniający dysk (sentinel zamiast prawdziwego
    # opisu — udaje przestarzałą treść z #329).
    tpl, _ = Template.objects.update_or_create(
        name="opis_bibliograficzny.html",
        defaults={"content": "STARY-SZABLON-MARKER"},
    )
    SzablonDlaOpisuBibliograficznego.objects.get_or_create(
        model=None, defaults={"template": tpl}
    )
    # dbtemplates cache (LocMem) nie jest rollbackowany między testami; wymuś,
    # by loader przeczytał świeżo wstawiony marker z bazy.
    wyczysc_cache_dbtemplate("opis_bibliograficzny.html")

    rebuild_instances_of_models([Wydawnictwo_Zwarte])
    denorms.flush()
    wydawnictwo_zwarte.refresh_from_db()
    assert "STARY-SZABLON-MARKER" in wydawnictwo_zwarte.opis_bibliograficzny_cache
    assert "Rodzic Z Dysku" not in wydawnictwo_zwarte.opis_bibliograficzny_cache

    call_command("drop_dbtemplate", "opis_bibliograficzny.html")

    wydawnictwo_zwarte.refresh_from_db()
    assert "W: Rodzic Z Dysku." in wydawnictwo_zwarte.opis_bibliograficzny_cache
    assert "STARY-SZABLON-MARKER" not in wydawnictwo_zwarte.opis_bibliograficzny_cache
