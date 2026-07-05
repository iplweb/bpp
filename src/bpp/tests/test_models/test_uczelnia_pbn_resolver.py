"""Testy dla ścisłego resolwera uczelni dla zadań PBN w tle.

W trybie multi-hosted KAŻDY entrypoint (widok) zna konkretną uczelnię
z requestu i MUSI przekazać jej ``pk`` do zadania Celery. Resolwer
``get_for_pbn_background`` świadomie NIE robi fallbacku do
``get_default()`` — wybór "pierwszej z brzegu" uczelni to właśnie ten
bug, przez który zadania pobierały konfigurację PBN złej uczelni.
"""

import pytest

from bpp.models import Uczelnia


@pytest.mark.django_db
def test_get_for_pbn_background_raises_without_id():
    """Brak uczelnia_id => ValueError, ZERO fallbacku do get_default()."""
    with pytest.raises(ValueError):
        Uczelnia.objects.get_for_pbn_background(None)


@pytest.mark.django_db
def test_get_for_pbn_background_returns_requested_uczelnia(uczelnia):
    """Z poprawnym id zwraca dokładnie tę uczelnię."""
    assert Uczelnia.objects.get_for_pbn_background(uczelnia.pk) == uczelnia


@pytest.mark.django_db
def test_get_for_pbn_background_does_not_fall_back_to_first(uczelnia):
    """Gdy istnieją dwie uczelnie, a id jest None — resolwer MUSI rzucić,
    a nie po cichu zwrócić pierwszą (to było źródłem błędu 403)."""
    from django.contrib.sites.models import Site

    site2, _ = Site.objects.get_or_create(
        domain="druga.example.com", defaults={"name": "druga"}
    )
    Uczelnia.objects.create(skrot="DR", nazwa="Druga uczelnia", site=site2)

    with pytest.raises(ValueError):
        Uczelnia.objects.get_for_pbn_background(None)


@pytest.mark.django_db
def test_get_for_pbn_background_raises_for_unknown_id(uczelnia):
    """Nieistniejące id => Uczelnia.DoesNotExist (nie cichy fallback)."""
    with pytest.raises(Uczelnia.DoesNotExist):
        Uczelnia.objects.get_for_pbn_background(uczelnia.pk + 9999)
