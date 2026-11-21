"""Kosz autora a historia wersji (django-reversion).

Przywrócenie wersji zapisuje cały obiekt z wersji, więc bez blokady
wyjęłoby autora z kosza z pominięciem ``Autor.restore()`` (guard,
SoftDeleteLog, kolejka PBN). Pola kosza nie są też częścią wersji.
"""

import pytest
import reversion
from django.contrib import admin as djadmin
from django.core.exceptions import PermissionDenied
from model_bakery import baker
from reversion.models import Version

from bpp.admin.autor import AutorAdmin
from bpp.models import Autor

pytestmark = pytest.mark.django_db


def test_pola_kosza_nie_sa_wersjonowane():
    autor = baker.make(Autor)
    with reversion.create_revision():
        autor.save()
    pola = Version.objects.get_for_object(autor).first().field_dict
    for nazwa in ("deleted_at", "restored_at", "transaction_id"):
        assert nazwa not in pola


def test_admin_nie_przywraca_wersji_autora_z_kosza(rf, admin_user):
    autor = baker.make(Autor)
    autor.delete()
    aa = AutorAdmin(Autor, djadmin.site)
    request = rf.post("/")
    request.user = admin_user
    with pytest.raises(PermissionDenied):
        aa.revision_view(request, str(autor.pk), "1")
    assert Autor.deleted_objects.filter(pk=autor.pk).exists()
