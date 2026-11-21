"""Kosz autora a historia wersji (django-reversion).

Pola kosza nie są częścią wersji autora. Blokadę przywracania wersji
rekordu z kosza w adminie dokłada faza 07 (kosz w adminie).
"""

import pytest
from reversion.revisions import _get_options

from bpp.models import Autor

pytestmark = pytest.mark.django_db


def test_pola_kosza_nie_sa_wersjonowane():
    pola = _get_options(Autor).fields
    for nazwa in ("deleted_at", "restored_at", "transaction_id"):
        assert nazwa not in pola
