"""Kosz autora a historia wersji (django-reversion).

Przywrócenie wersji zapisuje cały obiekt z wersji, więc bez blokady
wyjęłoby autora z kosza z pominięciem ``Autor.restore()`` (guard,
SoftDeleteLog, kolejka PBN). Pola kosza nie są też częścią wersji.
"""

import pytest
import reversion
from django.urls import reverse
from model_bakery import baker
from reversion.models import Version

from bpp.models import Autor

pytestmark = pytest.mark.django_db


def test_pola_kosza_nie_sa_wersjonowane():
    autor = baker.make(Autor)
    with reversion.create_revision():
        autor.save()
    pola = Version.objects.get_for_object(autor).first().field_dict
    for nazwa in ("deleted_at", "restored_at", "transaction_id"):
        assert nazwa not in pola


def test_admin_nie_przywraca_wersji_autora_z_kosza(admin_client):
    """Przywracanie wersji rekordu z kosza jest zablokowane — zamiast
    formularza powrót na stronę „Historia” z komunikatem (FD#587)."""
    autor = baker.make(Autor)
    with reversion.create_revision():
        autor.save()
    wersja = Version.objects.get_for_object(autor).get()
    autor.delete()
    url = reverse("admin:bpp_autor_revision", args=(autor.pk, wersja.pk))
    for metoda in (admin_client.get, admin_client.post):
        res = metoda(url)
        assert res.status_code == 302
        assert res.url == reverse("admin:bpp_autor_history", args=(autor.pk,))
    assert Autor.deleted_objects.filter(pk=autor.pk).exists()
