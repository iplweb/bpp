"""XSS #3 (audyt): tytuły w POZOSTAŁYCH językach (``BazaModeluTytulow`` →
``Wydawnictwo_Ciagle_Tytul`` / ``Wydawnictwo_Zwarte_Tytul``) są zapisywane
prosto z importu PBN (``objects.create(tytul=...)``) — bez ``full_clean()``.
Muszą być sanityzowane w ``save()`` (jak ``DwaTytuly``), a komenda
``sanityzuj_tytuly`` musi umieć wyczyścić także istniejące, brudne dane.
"""

import pytest
from django.core.management import call_command
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Tytul

XSS = "<script>alert(document.cookie)</script>Nowotwór"


@pytest.mark.django_db
def test_child_title_sanityzuje_sie_przy_create():
    # Ścieżka importera PBN: objects.create(tytul=...) — NIE woła full_clean().
    rekord = baker.make(Wydawnictwo_Ciagle)
    t = Wydawnictwo_Ciagle_Tytul.objects.create(rekord=rekord, tytul=XSS)
    t.refresh_from_db()
    assert "<script>" not in t.tytul
    assert "Nowotwór" in t.tytul


@pytest.mark.django_db
def test_sanityzuj_tytuly_czysci_legacy_child_title():
    # Dane sprzed wdrożenia save-hooka: wstrzyknięte surowym UPDATE (omija save()).
    rekord = baker.make(Wydawnictwo_Ciagle)
    t = Wydawnictwo_Ciagle_Tytul.objects.create(rekord=rekord, tytul="czysty")
    Wydawnictwo_Ciagle_Tytul.objects.filter(pk=t.pk).update(tytul=XSS)

    call_command("sanityzuj_tytuly", "--napraw")

    t.refresh_from_db()
    assert "<script>" not in t.tytul
    assert "Nowotwór" in t.tytul
