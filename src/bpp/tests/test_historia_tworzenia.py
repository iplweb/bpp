"""Historia (``LogEntry``/reversion) rekordów tworzonych poza adminem.

Rekordy tworzone przez importy, „Toż" itp. muszą mieć wpis na stronie
„Historia" w adminie — inaczej wyglądają, jakby pojawiły się znikąd. Gdy
nie znamy operatora (polecenia manage.py), wpis trafia do leniwie
tworzonego konta systemowego ``system-user-<login>``.
"""

import getpass

import pytest
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Wydawnictwo_Ciagle
from bpp.wersjonowanie import (
    ZNACZNIK_KONTA_SYSTEMOWEGO,
    jako_uzytkownik,
    konto_systemowe,
    zarejestruj_utworzenie,
)


def _wpisy(obj):
    return LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(obj),
        object_id=str(obj.pk),
    )


@pytest.fixture
def login_biblio(monkeypatch):
    monkeypatch.setattr(getpass, "getuser", lambda: "biblio")


@pytest.mark.django_db
def test_konto_systemowe_tworzone_leniwie_od_loginu(login_biblio):
    User = get_user_model()
    assert not User.objects.filter(username__startswith="system-user-").exists()

    konto = konto_systemowe()

    assert konto.username == "system-user-biblio"
    assert not konto.is_active
    assert not konto.has_usable_password()
    assert konto.adnotacje == ZNACZNIK_KONTA_SYSTEMOWEGO
    # Drugie wywołanie używa tego samego konta.
    assert konto_systemowe() == konto


@pytest.mark.django_db
def test_konto_systemowe_nazwa_zajeta_przez_zwykle_konto(login_biblio):
    baker.make(get_user_model(), username="system-user-biblio")

    assert konto_systemowe().username == "system-user-biblio-2"


@pytest.mark.django_db
def test_konto_systemowe_bez_loginu(monkeypatch):
    def brak_loginu():
        raise OSError("No username set in the environment")

    monkeypatch.setattr(getpass, "getuser", brak_loginu)
    monkeypatch.setattr("os.getuid", lambda: 1234)

    assert konto_systemowe().username == "system-user-uid1234"


@pytest.mark.django_db
def test_zarejestruj_utworzenie_bez_operatora_trafia_do_konta_systemowego(
    login_biblio,
):
    autor = baker.make(Autor)

    zarejestruj_utworzenie(None, autor, "Test.")

    wpis = _wpisy(autor).get()
    assert wpis.action_flag == ADDITION
    assert wpis.user.username == "system-user-biblio"


@pytest.mark.django_db
def test_jako_uzytkownik_wskazuje_autora_wpisu(admin_user):
    autor = baker.make(Autor)

    with jako_uzytkownik(admin_user):
        zarejestruj_utworzenie(None, autor, "Test.")

    assert _wpisy(autor).get().user == admin_user
    assert (
        not get_user_model()
        .objects.filter(username__startswith="system-user-")
        .exists()
    )


@pytest.mark.django_db
def test_toz_zapisuje_historie_kopii(admin_client, admin_user):
    oryginal = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca")

    response = admin_client.post(
        reverse("admin_bpp_wydawnictwo_ciagle_toz", args=(oryginal.pk,))
    )
    assert response.status_code == 302

    kopia = Wydawnictwo_Ciagle.objects.exclude(pk=oryginal.pk).get()
    wpis = _wpisy(kopia).get()
    assert wpis.action_flag == ADDITION
    assert wpis.user == admin_user
    assert f"kopię rekordu nr {oryginal.pk}" in wpis.change_message
