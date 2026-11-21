"""Deleting a dictionary entry that is still in use must be refused.

Dictionary FKs on publications and on the ``*_Autor`` link tables used to be
``on_delete=CASCADE``: deleting e.g. the "aut." responsibility type in the
admin silently deleted every authorship row using it (and deleting a language
deleted every publication in that language). They are ``PROTECT`` now.
"""

import pytest
from django.contrib.auth.models import Group
from django.db.models import ProtectedError
from django.urls import reverse
from model_bakery import baker

from bpp.models import Typ_Odpowiedzialnosci, Wydawnictwo_Ciagle_Autor

pytestmark = pytest.mark.django_db


@pytest.fixture
def nowy_typ_odpowiedzialnosci(db):
    return baker.make(Typ_Odpowiedzialnosci, nazwa="testowy typ", skrot="tst.")


@pytest.fixture
def autorstwo(
    wydawnictwo_ciagle, autor_jan_kowalski, jednostka, nowy_typ_odpowiedzialnosci
):
    return wydawnictwo_ciagle.dodaj_autora(
        autor_jan_kowalski,
        jednostka,
        typ_odpowiedzialnosci_skrot=nowy_typ_odpowiedzialnosci.skrot,
    )


@pytest.fixture
def admin_z_grupa_administracja(admin_user, client):
    # RestrictDeletionToAdministracjaGroupMixin: deleting dictionary entries
    # requires the "administracja" group, even for a superuser.
    grupa, _ = Group.objects.get_or_create(name="administracja")
    admin_user.groups.add(grupa)
    client.force_login(admin_user)
    return client


def _delete_url(obj):
    return reverse("admin:bpp_typ_odpowiedzialnosci_delete", args=[obj.pk])


def test_typ_odpowiedzialnosci_w_uzyciu_orm_protect(
    autorstwo, nowy_typ_odpowiedzialnosci
):
    with pytest.raises(ProtectedError):
        nowy_typ_odpowiedzialnosci.delete()

    assert Wydawnictwo_Ciagle_Autor.objects.filter(pk=autorstwo.pk).exists()
    assert Typ_Odpowiedzialnosci.objects.filter(
        pk=nowy_typ_odpowiedzialnosci.pk
    ).exists()


def test_typ_odpowiedzialnosci_w_uzyciu_admin_odmawia(
    autorstwo, nowy_typ_odpowiedzialnosci, admin_z_grupa_administracja
):
    client = admin_z_grupa_administracja
    url = _delete_url(nowy_typ_odpowiedzialnosci)

    res = client.get(url)
    assert res.status_code == 200
    assert res.context["protected"]

    res = client.post(url, {"post": "yes"})
    # Django shows the "cannot delete, protected objects" page, not a 500
    # and not a redirect after deleting.
    assert res.status_code == 200
    assert res.context["protected"]

    assert Typ_Odpowiedzialnosci.objects.filter(
        pk=nowy_typ_odpowiedzialnosci.pk
    ).exists()
    assert Wydawnictwo_Ciagle_Autor.objects.filter(pk=autorstwo.pk).exists()


def test_typ_odpowiedzialnosci_nieuzywany_admin_usuwa(
    nowy_typ_odpowiedzialnosci, admin_z_grupa_administracja
):
    client = admin_z_grupa_administracja
    res = client.post(_delete_url(nowy_typ_odpowiedzialnosci), {"post": "yes"})

    assert res.status_code == 302
    assert not Typ_Odpowiedzialnosci.objects.filter(
        pk=nowy_typ_odpowiedzialnosci.pk
    ).exists()


@pytest.mark.parametrize(
    "pole", ["jezyk", "typ_kbn", "charakter_formalny", "status_korekty"]
)
def test_slownik_publikacji_w_uzyciu_protect(wydawnictwo_ciagle, pole):
    slownik = getattr(wydawnictwo_ciagle, pole)

    with pytest.raises(ProtectedError):
        slownik.delete()

    assert type(wydawnictwo_ciagle).objects.filter(pk=wydawnictwo_ciagle.pk).exists()


def test_jednostka_w_autorstwie_protect(autorstwo, jednostka):
    with pytest.raises(ProtectedError):
        jednostka.delete()

    assert Wydawnictwo_Ciagle_Autor.objects.filter(pk=autorstwo.pk).exists()
