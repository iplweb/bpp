"""Hub „przegląd importu" (PodgladImportuView, T2.2/T2.5)."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowJednostka,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
    ImportPracownikowTytul,
)
from import_pracownikow.pewnosc import (
    STATUS_BRAK,
    STATUS_TWARDY,
    STATUS_WIELU,
    STATUS_ZGADYWANIE,
)


def _imp(owner, stan=ImportPracownikow.STAN_PRZEANALIZOWANY):
    return baker.make(ImportPracownikow, owner=owner, stan=stan)


def _url(imp):
    return reverse("import_pracownikow:przeglad", kwargs={"pk": imp.pk})


def _row(imp, confidence, **kw):
    return baker.make(
        ImportPracownikowRow,
        parent=imp,
        confidence=confidence,
        zmiany_potrzebne=False,
        **kw,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "stan",
    [
        ImportPracownikow.STAN_UTWORZONY,
        ImportPracownikow.STAN_ZMAPOWANY,
        ImportPracownikow.STAN_PRZEANALIZOWANY,
        ImportPracownikow.STAN_ZATWIERDZONY,
        ImportPracownikow.STAN_ZINTEGROWANY,
        ImportPracownikow.STAN_PORZUCONY,
    ],
)
def test_hub_renderuje_sie_w_kazdym_stanie(admin_client, admin_user, stan):
    imp = _imp(admin_user, stan=stan)
    resp = admin_client.get(_url(imp))
    # Hub nie może się wywalać (NoReverseMatch itp.) w żadnym stanie.
    assert resp.status_code == 200
    assert imp.get_stan_display().encode() in resp.content


@pytest.mark.django_db
def test_kafelek_jednostki_ukryty_gdy_zero_decyzji(admin_client, admin_user):
    imp = _imp(admin_user)
    resp = admin_client.get(_url(imp))
    tresc = resp.content.decode("utf-8")
    assert reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk}) not in tresc


@pytest.mark.django_db
def test_kafelek_jednostki_widoczny_z_licznikami(admin_client, admin_user):
    imp = _imp(admin_user)
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        nazwa_zrodlowa="A",
        tryb=ImportPracownikowJednostka.TRYB_BRAK,
        utworzona=None,
    )
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        nazwa_zrodlowa="B",
        tryb=ImportPracownikowJednostka.TRYB_BRAK,
        utworzona=None,
    )
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        nazwa_zrodlowa="C",
        tryb=ImportPracownikowJednostka.TRYB_ZGADYWANIE,
        utworzona=None,
    )
    resp = admin_client.get(_url(imp))
    tresc = resp.content.decode("utf-8")
    assert reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk}) in tresc
    assert "2 do utworzenia" in tresc
    assert "1 do sprawdzenia" in tresc


@pytest.mark.django_db
def test_kafelek_tytuly_ukryty_gdy_zero_decyzji(admin_client, admin_user):
    imp = _imp(admin_user)
    resp = admin_client.get(_url(imp))
    tresc = resp.content.decode("utf-8")
    assert reverse("import_pracownikow:tytuly", kwargs={"pk": imp.pk}) not in tresc


@pytest.mark.django_db
def test_kafelek_tytuly_widoczny_z_licznikami(admin_client, admin_user):
    imp = _imp(admin_user)
    baker.make(
        ImportPracownikowTytul,
        parent=imp,
        nazwa_zrodlowa="a",
        tryb=ImportPracownikowTytul.TRYB_BRAK,
        utworzony=None,
    )
    baker.make(
        ImportPracownikowTytul,
        parent=imp,
        nazwa_zrodlowa="b",
        tryb=ImportPracownikowTytul.TRYB_ZGADYWANIE,
        utworzony=None,
    )
    resp = admin_client.get(_url(imp))
    tresc = resp.content.decode("utf-8")
    assert reverse("import_pracownikow:tytuly", kwargs={"pk": imp.pk}) in tresc


@pytest.mark.django_db
def test_liczniki_ludzi_zgodne_z_danymi(admin_client, admin_user):
    # Kafelek osób odsłania się w fazie osób (po zapisaniu struktury).
    imp = _imp(admin_user, stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA)
    _row(imp, STATUS_TWARDY)
    _row(imp, STATUS_TWARDY)
    _row(imp, STATUS_ZGADYWANIE)
    _row(imp, STATUS_WIELU)
    _row(imp, STATUS_BRAK)
    resp = admin_client.get(_url(imp))
    tresc = resp.content.decode("utf-8")
    assert "2 pewnych" in tresc
    assert "1 luźnych" in tresc
    # do akceptacji = wielu (1) + brak (1) = 2
    assert "2 do akceptacji" in tresc


@pytest.mark.django_db
def test_ludzie_gotowe_gdy_zero_do_akceptacji(admin_client, admin_user):
    imp = _imp(admin_user, stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA)
    _row(imp, STATUS_TWARDY)
    _row(imp, STATUS_ZGADYWANIE)
    resp = admin_client.get(_url(imp))
    tresc = resp.content.decode("utf-8")
    assert "0 do akceptacji" in tresc
    assert "gotowe" in tresc


@pytest.mark.django_db
def test_krok1_struktura_w_przeanalizowany(admin_client, admin_user):
    """W podglądzie (Krok 1) hub oferuje TYLKO zapis struktury — dwa przyciski
    strukturalne, BEZ importu osób (pelny). Import osób jest zablokowany."""
    imp = _imp(admin_user, stan=ImportPracownikow.STAN_PRZEANALIZOWANY)
    resp = admin_client.get(_url(imp))
    tresc = resp.content.decode("utf-8")
    assert reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk}) in tresc
    assert 'value="jednostki"' in tresc
    assert 'value="struktura"' in tresc
    assert "Zapisz tylko jednostki" in tresc
    assert "Zapisz jednostki + tytuły" in tresc
    # import osób (pelny) NIE jest tu dostępny — dopiero po zapisie struktury
    assert 'value="pelny"' not in tresc
    assert "Zapisz osoby do bazy" not in tresc
    # Krok 2 zapowiedziany jako zablokowany
    assert "Krok 2 — osoby" in tresc


@pytest.mark.django_db
def test_krok2_import_osob_w_strukturze_zintegrowanej(admin_client, admin_user):
    """Po zapisaniu struktury (struktura_zintegrowana) odblokowany jest import
    osób (Krok 2) — przycisk „Zapisz osoby do bazy" z zakresem pelny."""
    imp = _imp(admin_user, stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA)
    resp = admin_client.get(_url(imp))
    tresc = resp.content.decode("utf-8")
    assert 'value="pelny"' in tresc
    assert "Zapisz osoby do bazy" in tresc
    # kafelki osób odsłonięte
    assert (
        reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
        in tresc
    )
    # struktura NIE jest tu do zapisania po raz drugi
    assert 'value="jednostki"' not in tresc


@pytest.mark.django_db
def test_hub_ukrywa_osoby_w_przeanalizowany(admin_client, admin_user):
    """Regresja: w podglądzie (Krok 1) szczegóły osób są UKRYTE — brak linków do
    listy wierszy i odpięć, dopóki struktura nie zostanie zapisana."""
    imp = _imp(admin_user, stan=ImportPracownikow.STAN_PRZEANALIZOWANY)
    resp = admin_client.get(_url(imp))
    tresc = resp.content.decode("utf-8")
    assert (
        reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
        not in tresc
    )
    assert reverse("import_pracownikow:odpiecia", kwargs={"pk": imp.pk}) not in tresc


@pytest.mark.django_db
def test_cta_zapisz_brak_poza_faza_akcji(admin_client, admin_user):
    """Po pełnej integracji (zintegrowany) nie ma już żadnych przycisków akcji."""
    imp = _imp(admin_user, stan=ImportPracownikow.STAN_ZINTEGROWANY)
    resp = admin_client.get(_url(imp))
    tresc = resp.content.decode("utf-8")
    assert "Zapisz osoby do bazy" not in tresc
    assert 'value="jednostki"' not in tresc
    assert 'value="pelny"' not in tresc


@pytest.mark.django_db
def test_ostrzezenie_gdy_pary_z_pliku_puste_a_odpiecia_sa(admin_client, admin_user):
    # kafelek „Ludzie spoza XLS" (z ostrzeżeniem) jest w fazie osób.
    imp = _imp(admin_user, stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA)
    # brak wierszy z autorem+jednostką → pary_z_pliku puste
    aj = baker.make(Autor_Jednostka, autor__nazwisko="Spozaplikowy")
    ImportPracownikowOdpiecie.objects.create(parent=imp, autor_jednostka=aj)
    resp = admin_client.get(_url(imp))
    tresc = resp.content.decode("utf-8")
    assert "może być zawyżona" in tresc


@pytest.mark.django_db
def test_brak_ostrzezenia_gdy_sa_pary_z_pliku(admin_client, admin_user):
    imp = _imp(admin_user, stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA)
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    _row(imp, STATUS_TWARDY, autor=autor, jednostka=jednostka)  # para z pliku
    aj = baker.make(Autor_Jednostka, autor__nazwisko="Spozaplikowy")
    ImportPracownikowOdpiecie.objects.create(parent=imp, autor_jednostka=aj)
    resp = admin_client.get(_url(imp))
    tresc = resp.content.decode("utf-8")
    assert "może być zawyżona" not in tresc


@pytest.mark.django_db
def test_scoping_obcy_import_404(client, django_user_model, admin_user):
    imp = _imp(admin_user)
    obcy = django_user_model.objects.create_user(
        username="obcy_hub", password="x", is_superuser=False
    )
    from django.contrib.auth.models import Group

    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    obcy.groups.add(grupa)
    client.force_login(obcy)
    resp = client.get(_url(imp))
    assert resp.status_code == 404
