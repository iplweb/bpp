"""Powiązania z PBN ustawiane przez integrator trafiają do historii admina."""

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from model_bakery import baker
from reversion.models import Version

from bpp.models import Autor, Wydawca
from bpp.wersjonowanie import jako_uzytkownik
from pbn_api.models import Publisher, Scientist
from pbn_integrator.utils.publishers import _powiaz_wydawce
from pbn_integrator.utils.scientists import _powiaz_autora_z_pbn


@pytest.mark.django_db
def test_powiazanie_autora_z_pbn(admin_user):
    scientist = baker.make(Scientist, mongoId="sci-int-1")
    autor = baker.make(Autor)

    with jako_uzytkownik(admin_user):
        _powiaz_autora_z_pbn(autor, scientist.pk, "integracja autorów")

    wpis = LogEntry.objects.get(content_type__model="autor", object_id=str(autor.pk))
    assert wpis.action_flag == CHANGE
    assert wpis.user == admin_user
    assert "sci-int-1 (integracja autorów)" in wpis.change_message
    assert Version.objects.get_for_object(autor).count() == 2


@pytest.mark.django_db
def test_powiazanie_wydawcy_z_pbn_bez_uzytkownika(monkeypatch):
    import getpass

    monkeypatch.setattr(getpass, "getuser", lambda: "biblio")
    publisher = baker.make(Publisher, mongoId="pub-int-1")
    wydawca = baker.make(Wydawca, pbn_uid=None)

    _powiaz_wydawce(wydawca, publisher.pk)

    wydawca.refresh_from_db()
    assert wydawca.pbn_uid_id == "pub-int-1"
    wpis = LogEntry.objects.get(
        content_type__model="wydawca", object_id=str(wydawca.pk)
    )
    assert wpis.user.username == "system-user-biblio"
