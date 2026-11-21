"""Akcje masowe admina (``zmien_hurtowo_z_historia``) pomijają rekordy z kosza.

Rekord w koszu jest zamrożony triggerem ``bpp_kosz_straznik`` — hurtowy
``UPDATE`` obejmujący go wywaliłby się błędem bazy (500 w adminie).
Zaznaczenie z filtrem „Kosz” może takie rekordy zawierać.
"""

import pytest
from model_bakery import baker

from bpp.admin.actions import ustaw_status, zmien_hurtowo_z_historia
from bpp.models import Autor, Status_Korekty, Wydawnictwo_Ciagle

pytestmark = pytest.mark.django_db


def test_akcja_masowa_autora_pomija_kosz(rf, admin_user):
    zywy = baker.make(Autor, pokazuj_na_stronie_jednostki=True)
    w_koszu = baker.make(Autor, pokazuj_na_stronie_jednostki=True)
    w_koszu.delete()
    request = rf.post("/")
    request.user = admin_user

    zmieniono = zmien_hurtowo_z_historia(
        request,
        Autor.global_objects.filter(pk__in=[zywy.pk, w_koszu.pk]),
        {"pokazuj_na_stronie_jednostki": False},
        "test",
    )

    assert zmieniono == 1
    assert not Autor.objects.get(pk=zywy.pk).pokazuj_na_stronie_jednostki
    assert Autor.global_objects.get(pk=w_koszu.pk).pokazuj_na_stronie_jednostki


def test_ustaw_status_korekty_pomija_kosz(rf, admin_user):
    nowy = Status_Korekty.objects.get_or_create(nazwa="po korekcie")[0]
    zywa = baker.make(Wydawnictwo_Ciagle)
    w_koszu = baker.make(Wydawnictwo_Ciagle)
    w_koszu.delete()
    request = rf.post("/")
    request.user = admin_user

    zmieniono = ustaw_status(
        request,
        Wydawnictwo_Ciagle.global_objects.filter(pk__in=[zywa.pk, w_koszu.pk]),
        nowy.nazwa,
    )

    assert zmieniono == 1
    assert Wydawnictwo_Ciagle.objects.get(pk=zywa.pk).status_korekty == nowy
    assert Wydawnictwo_Ciagle.global_objects.get(pk=w_koszu.pk).status_korekty != nowy
