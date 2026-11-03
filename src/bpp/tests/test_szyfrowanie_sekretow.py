import importlib
import pickle
from io import StringIO

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from model_bakery import baker

from bpp import checks as bpp_checks
from bpp.fields import EncryptedTextField, NieodszyfrowanaWartosc
from bpp.models import BppUser, Uczelnia

PREFIKS = "gAAAAA"


@pytest.fixture
def klucz(settings):
    settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
    settings.DSPACE_CREDENTIALS_KEY = ""
    return settings.FIELD_ENCRYPTION_KEY


@pytest.fixture
def bez_klucza(settings):
    settings.FIELD_ENCRYPTION_KEY = ""
    settings.DSPACE_CREDENTIALS_KEY = ""


def _surowa(tabela, kolumna, pk):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {kolumna} FROM {tabela} WHERE id = %s", [pk])
        return cursor.fetchone()[0]


def _ustaw_surowa(tabela, kolumna, pk, wartosc):
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {tabela} SET {kolumna} = %s WHERE id = %s", [wartosc, pk]
        )


# --- pole ---------------------------------------------------------------


def test_pole_jawna_wartosc_z_bazy_zwracana_wprost(klucz):
    f = EncryptedTextField()
    assert f.from_db_value("jawny-token", None, connection) == "jawny-token"


def test_pole_bez_klucza_zapisuje_jawnie(bez_klucza):
    f = EncryptedTextField()
    assert f.get_prep_value("token") == "token"
    assert f.from_db_value("token", None, connection) == "token"


def test_pole_multifernet_czyta_starym_kluczem_szyfruje_nowym(settings):
    stary = Fernet.generate_key().decode()
    nowy = Fernet.generate_key().decode()
    settings.FIELD_ENCRYPTION_KEY = ""
    settings.DSPACE_CREDENTIALS_KEY = stary
    f = EncryptedTextField()
    szyfrogram_stary = f.get_prep_value("sekret")

    settings.FIELD_ENCRYPTION_KEY = nowy
    assert f.from_db_value(szyfrogram_stary, None, connection) == "sekret"
    szyfrogram_nowy = f.get_prep_value("sekret")
    assert Fernet(nowy.encode()).decrypt(szyfrogram_nowy.encode()) == b"sekret"


def test_pole_kilka_kluczy_po_przecinku(settings):
    stary = Fernet.generate_key().decode()
    nowy = Fernet.generate_key().decode()
    settings.DSPACE_CREDENTIALS_KEY = ""
    settings.FIELD_ENCRYPTION_KEY = stary
    szyfrogram = EncryptedTextField().get_prep_value("x")
    settings.FIELD_ENCRYPTION_KEY = f"{nowy}, {stary}"
    assert EncryptedTextField().from_db_value(szyfrogram, None, connection) == "x"


def test_pole_zly_format_klucza(settings):
    settings.FIELD_ENCRYPTION_KEY = "to-nie-jest-klucz"
    with pytest.raises(ImproperlyConfigured):
        EncryptedTextField().get_prep_value("x")


def test_pole_nieodszyfrowalne_puste_ale_zachowuje_szyfrogram(klucz, settings):
    f = EncryptedTextField()
    szyfrogram = f.get_prep_value("sekret")
    settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()

    odczyt = f.from_db_value(szyfrogram, None, connection)
    assert odczyt == ""
    assert not odczyt
    assert isinstance(odczyt, NieodszyfrowanaWartosc)
    assert f.get_prep_value(odczyt) == szyfrogram
    assert pickle.loads(pickle.dumps(odczyt)).szyfrogram == szyfrogram


def test_pole_nie_szyfruje_podwojnie(klucz):
    f = EncryptedTextField()
    szyfrogram = f.get_prep_value("sekret")
    assert f.get_prep_value(szyfrogram) == szyfrogram


# --- modele -------------------------------------------------------------


@pytest.mark.django_db
def test_uczelnia_sekrety_zaszyfrowane_w_bazie(klucz):
    pola = ("pbn_app_token", "orcid_client_secret", "clarivate_password")
    wartosci = {pole: f"wartosc-{pole}" for pole in pola}
    u = baker.make(Uczelnia, **wartosci)
    for kolumna in pola:
        assert _surowa("bpp_uczelnia", kolumna, u.pk).startswith(PREFIKS)

    u.refresh_from_db()
    for pole in pola:
        assert getattr(u, pole) == wartosci[pole]


@pytest.mark.django_db
def test_bppuser_pbn_token_zaszyfrowany_i_filtr_po_pustym(klucz):
    z_tokenem = baker.make(BppUser, pbn_token="user-token")
    bez_tokena = baker.make(BppUser, pbn_token="")

    assert _surowa("bpp_bppuser", "pbn_token", z_tokenem.pk).startswith(PREFIKS)
    assert _surowa("bpp_bppuser", "pbn_token", bez_tokena.pk) == ""

    pks = set(BppUser.objects.exclude(pbn_token="").values_list("pk", flat=True))
    assert z_tokenem.pk in pks
    assert bez_tokena.pk not in pks
    assert BppUser.objects.filter(pbn_token="", pk=bez_tokena.pk).exists()

    z_tokenem.refresh_from_db()
    assert z_tokenem.pbn_token == "user-token"


@pytest.mark.django_db
def test_bppuser_update_queryset_szyfruje(klucz):
    user = baker.make(BppUser)
    BppUser.objects.filter(pk=user.pk).update(pbn_token="nowy")
    assert _surowa("bpp_bppuser", "pbn_token", user.pk).startswith(PREFIKS)
    user.refresh_from_db()
    assert user.pbn_token == "nowy"


@pytest.mark.django_db
def test_bppuser_jawny_token_z_bazy_czytelny(klucz):
    user = baker.make(BppUser)
    _ustaw_surowa("bpp_bppuser", "pbn_token", user.pk, "stary-jawny")
    user.refresh_from_db()
    assert user.pbn_token == "stary-jawny"


@pytest.mark.django_db
def test_zapis_rekordu_nie_niszczy_nieodszyfrowalnego_sekretu(klucz, settings):
    u = baker.make(Uczelnia, pbn_app_token="app-token")
    szyfrogram = _surowa("bpp_uczelnia", "pbn_app_token", u.pk)

    settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
    u = Uczelnia.objects.get(pk=u.pk)
    assert u.pbn_app_token == ""
    u.nazwa = "Zmieniona"
    u.save()
    assert _surowa("bpp_uczelnia", "pbn_app_token", u.pk) == szyfrogram


@pytest.mark.django_db
def test_pbn_client_dostaje_odszyfrowane_tokeny(klucz):
    u = baker.make(
        Uczelnia,
        pbn_integracja=True,
        pbn_app_name="app",
        pbn_app_token="app-token",
    )
    u.refresh_from_db()
    client = u.pbn_client("user-token")
    wartosci = set(vars(client.transport).values())
    assert "app-token" in wartosci
    assert "user-token" in wartosci


# --- migracja -----------------------------------------------------------


def _migracja():
    return importlib.import_module(
        "bpp.migrations.0497_uczelnia_bppuser_szyfrowanie_sekretow"
    )


@pytest.mark.django_db
def test_migracja_szyfruje_jawne_i_cofa(klucz):
    from django.apps import apps

    user = baker.make(BppUser)
    _ustaw_surowa("bpp_bppuser", "pbn_token", user.pk, "jawny")

    class SE:
        pass

    se = SE()
    se.connection = connection

    _migracja().zaszyfruj(apps, se)
    surowa = _surowa("bpp_bppuser", "pbn_token", user.pk)
    assert surowa.startswith(PREFIKS)
    user.refresh_from_db()
    assert user.pbn_token == "jawny"

    # idempotencja
    _migracja().zaszyfruj(apps, se)
    assert _surowa("bpp_bppuser", "pbn_token", user.pk) == surowa

    _migracja().odszyfruj(apps, se)
    assert _surowa("bpp_bppuser", "pbn_token", user.pk) == "jawny"


@pytest.mark.django_db
def test_migracja_bez_klucza_zostawia_jawne(bez_klucza, capsys):
    from django.apps import apps

    user = baker.make(BppUser)
    _ustaw_surowa("bpp_bppuser", "pbn_token", user.pk, "jawny")

    class SE:
        pass

    se = SE()
    se.connection = connection
    _migracja().zaszyfruj(apps, se)
    assert _surowa("bpp_bppuser", "pbn_token", user.pk) == "jawny"
    assert "zaszyfruj_sekrety" in capsys.readouterr().out


# --- komenda ------------------------------------------------------------


@pytest.mark.django_db
def test_komenda_szyfruje_jawne(klucz):
    user = baker.make(BppUser)
    u = baker.make(Uczelnia)
    _ustaw_surowa("bpp_bppuser", "pbn_token", user.pk, "jawny")
    _ustaw_surowa("bpp_uczelnia", "orcid_client_secret", u.pk, "orcid")

    call_command("zaszyfruj_sekrety", stdout=StringIO())

    assert _surowa("bpp_bppuser", "pbn_token", user.pk).startswith(PREFIKS)
    assert _surowa("bpp_uczelnia", "orcid_client_secret", u.pk).startswith(PREFIKS)
    u.refresh_from_db()
    assert u.orcid_client_secret == "orcid"


@pytest.mark.django_db
def test_komenda_dry_run_nic_nie_zapisuje(klucz):
    user = baker.make(BppUser)
    _ustaw_surowa("bpp_bppuser", "pbn_token", user.pk, "jawny")
    call_command("zaszyfruj_sekrety", "--dry-run", stdout=StringIO())
    assert _surowa("bpp_bppuser", "pbn_token", user.pk) == "jawny"


@pytest.mark.django_db
def test_komenda_bez_klucza_blad(bez_klucza):
    with pytest.raises(CommandError):
        call_command("zaszyfruj_sekrety", stdout=StringIO())


@pytest.mark.django_db
def test_komenda_rotuj_przepisuje_na_glowny_klucz(settings):
    stary = Fernet.generate_key().decode()
    nowy = Fernet.generate_key().decode()
    settings.DSPACE_CREDENTIALS_KEY = ""
    settings.FIELD_ENCRYPTION_KEY = stary
    user = baker.make(BppUser, pbn_token="token")

    settings.FIELD_ENCRYPTION_KEY = f"{nowy},{stary}"
    call_command("zaszyfruj_sekrety", "--rotuj", stdout=StringIO())

    surowa = _surowa("bpp_bppuser", "pbn_token", user.pk)
    assert Fernet(nowy.encode()).decrypt(surowa.encode()) == b"token"

    settings.FIELD_ENCRYPTION_KEY = nowy
    user.refresh_from_db()
    assert user.pbn_token == "token"


# --- system check -------------------------------------------------------


def test_check_brak_klucza(bez_klucza):
    wynik = bpp_checks.klucz_szyfrowania_check(None)
    assert [w.id for w in wynik] == [bpp_checks.W_BRAK_KLUCZA]


def test_check_zly_klucz(settings):
    settings.FIELD_ENCRYPTION_KEY = "zly"
    wynik = bpp_checks.klucz_szyfrowania_check(None)
    assert [w.id for w in wynik] == [bpp_checks.W_ZLY_KLUCZ]


def test_check_klucz_ok(klucz):
    assert bpp_checks.klucz_szyfrowania_check(None) == []


def test_check_bazy_bez_databases_nic_nie_robi(klucz):
    # Bez listy baz (np. collectstatic, runserver) check nie dotyka bazy.
    assert bpp_checks.sekrety_w_bazie_check(None, databases=None) == []


@pytest.mark.django_db
def test_check_bazy_wykrywa_nieodszyfrowalne_i_jawne(klucz, settings):
    zaszyfrowany = baker.make(BppUser, pbn_token="token")
    jawny = baker.make(BppUser)
    _ustaw_surowa("bpp_bppuser", "pbn_token", jawny.pk, "jawny")

    wynik = bpp_checks.sekrety_w_bazie_check(None, databases=["default"])
    assert [w.id for w in wynik] == [bpp_checks.W_JAWNE]

    settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
    wynik = bpp_checks.sekrety_w_bazie_check(None, databases=["default"])
    ids = [w.id for w in wynik]
    assert bpp_checks.W_NIEODSZYFROWALNE in ids
    assert zaszyfrowany.pk  # rekord nadal istnieje, check niczego nie zmienia


# --- serializacja / historia zmian --------------------------------------


@pytest.mark.django_db
def test_serializacja_zapisuje_szyfrogram_i_odtwarza_wartosc(klucz):
    from django.core import serializers

    u = baker.make(Uczelnia, pbn_app_token="app-token-xyz")
    u.refresh_from_db()
    dane = serializers.serialize("json", [u])
    assert "app-token-xyz" not in dane

    obj = next(serializers.deserialize("json", dane)).object
    assert obj.pbn_app_token == "app-token-xyz"
    obj.save()
    u.refresh_from_db()
    assert u.pbn_app_token == "app-token-xyz"


@pytest.mark.django_db
def test_historia_reversion_bez_jawnego_sekretu(klucz):
    import reversion
    from reversion.models import Version

    u = baker.make(Uczelnia)
    u.refresh_from_db()
    if not reversion.is_registered(Uczelnia):
        reversion.register(Uczelnia)
    u.orcid_client_secret = "orcid-secret-xyz"
    with reversion.create_revision():
        u.save()

    wersja = Version.objects.get_for_object(u).first()
    assert "orcid-secret-xyz" not in wersja.serialized_data

    Uczelnia.objects.filter(pk=u.pk).update(orcid_client_secret="")
    wersja.revert()
    u.refresh_from_db()
    assert u.orcid_client_secret == "orcid-secret-xyz"
