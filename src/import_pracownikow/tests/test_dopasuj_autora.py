import pytest
from django.urls import NoReverseMatch, reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
)
from import_pracownikow.pewnosc import STATUS_BRAK, STATUS_TWARDY, STATUS_WIELU


def _import(owner, stan=ImportPracownikow.STAN_PRZEANALIZOWANY):
    return baker.make(
        ImportPracownikow, owner=owner, stan=stan, finished_successfully=True
    )


def _row(imp, jednostka, **kw):
    defaults = dict(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_BRAK,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Jan", "nazwisko": "Kowalski"},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 1},
        diff_do_utworzenia={},
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    defaults.update(kw)
    return ImportPracownikowRow.objects.create(**defaults)


def _url(imp, row):
    return reverse(
        "import_pracownikow:dopasuj-autora",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )


def _results(client, imp):
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    return client.get(url).content.decode("utf-8")


# --- T1.2: DopasujAutoraView -------------------------------------------------


@pytest.mark.django_db
def test_dopasuj_autora_wiaze_i_odklada_aj(admin_client, admin_user):
    # Autor bez Autor_Jednostka → create AJ odłożony w diff, zmiany_potrzebne.
    imp = _import(admin_user)
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Anna")
    row = _row(imp, jednostka, confidence=STATUS_BRAK)
    resp = admin_client.post(_url(imp, row), {"autor": autor.pk})
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.autor_id == autor.pk
    assert row.confidence == STATUS_TWARDY
    assert row.autor_jednostka is None
    assert row.diff_do_utworzenia["autor_jednostka"]["autor"] == autor.pk
    assert row.zmiany_potrzebne is True
    assert row.utworz_nowego is False
    assert row.przepnij_prace is False


@pytest.mark.django_db
def test_dopasuj_autora_uzywa_istniejacego_aj(admin_client, admin_user):
    imp = _import(admin_user)
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Anna")
    aj = baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka)
    row = _row(imp, jednostka)
    resp = admin_client.post(_url(imp, row), {"autor": autor.pk})
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.autor_id == autor.pk
    assert row.autor_jednostka_id == aj.pk
    assert "autor_jednostka" not in row.diff_do_utworzenia


@pytest.mark.django_db
def test_dopasuj_autora_guard_jednostka_none(admin_client, admin_user):
    # GUARD: wiersz z odroczoną jednostką (jednostka=None) NIE może dostać
    # diff {"jednostka": None} ani liczyć zmian — integracja
    # get_or_create(jednostka_id=None) → IntegrityError ubijający task.
    imp = _import(admin_user)
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Anna")
    row = _row(imp, None, confidence=STATUS_WIELU)
    resp = admin_client.post(_url(imp, row), {"autor": autor.pk})
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.autor_id == autor.pk
    assert row.confidence == STATUS_TWARDY
    assert row.autor_jednostka is None
    assert "autor_jednostka" not in row.diff_do_utworzenia
    assert "jednostka" not in row.diff_do_utworzenia
    assert row.zmiany_potrzebne is False


@pytest.mark.django_db
def test_dopasuj_autora_owner_scoped(client, django_user_model, admin_user):
    imp = _import(admin_user)
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Anna")
    row = _row(imp, jednostka)
    inny = django_user_model.objects.create_user(
        username="inny", password="x", is_staff=True
    )
    from django.contrib.auth.models import Group

    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    inny.groups.add(grupa)
    client.force_login(inny)
    resp = client.post(_url(imp, row), {"autor": autor.pk})
    assert resp.status_code == 404
    row.refresh_from_db()
    assert row.autor is None


@pytest.mark.django_db
def test_dopasuj_autora_bramka_stanu(admin_client, admin_user):
    # G3: POST na imporcie już zintegrowanym MUSI dać 400 i nie mutować wiersza.
    imp = _import(admin_user, stan=ImportPracownikow.STAN_ZINTEGROWANY)
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Anna")
    row = _row(imp, jednostka)
    resp = admin_client.post(_url(imp, row), {"autor": autor.pk})
    assert resp.status_code == 400
    row.refresh_from_db()
    assert row.autor is None


@pytest.mark.django_db
def test_dopasuj_autora_zly_pk_404(admin_client, admin_user):
    imp = _import(admin_user)
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    row = _row(imp, jednostka)
    resp = admin_client.post(_url(imp, row), {"autor": 999999})
    assert resp.status_code == 404
    row.refresh_from_db()
    assert row.autor is None


# --- T1.3: usunięcie edycji XLS ---------------------------------------------


def test_edytuj_wiersz_url_usuniety():
    # Regres: endpoint edycji rozbicia XLS został usunięty.
    with pytest.raises(NoReverseMatch):
        reverse(
            "import_pracownikow:edytuj-wiersz",
            kwargs={"pk": "00000000-0000-0000-0000-000000000000", "row_pk": 1},
        )


# --- T1.4: render partiala per stan -----------------------------------------


@pytest.mark.django_db
def test_partial_brak_ma_autocomplete_i_checkbox_bez_freetext(admin_client, admin_user):
    imp = _import(admin_user)
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    row = _row(imp, jednostka, confidence=STATUS_BRAK)
    tresc = _results(admin_client, imp)
    assert reverse("bpp:import-autor-autocomplete") in tresc
    assert _url(imp, row) in tresc
    assert (
        reverse(
            "import_pracownikow:utworz-nowego",
            kwargs={"pk": imp.pk, "row_pk": row.pk},
        )
        in tresc
    )
    # BRAK pól free-text (usunięta edycja rozbicia XLS).
    assert 'name="imiona"' not in tresc
    assert 'name="nazwisko"' not in tresc
    assert 'name="tytul"' not in tresc


@pytest.mark.django_db
def test_partial_wielu_ma_dropdown_i_inny_autor(admin_client, admin_user):
    imp = _import(admin_user)
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    a1 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    row = _row(imp, jednostka, autor=None, confidence=STATUS_WIELU)
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=a1, pewnosc=1.0, powod="iexact"
    )
    tresc = _results(admin_client, imp)
    assert (
        reverse(
            "import_pracownikow:wybierz-kandydata",
            kwargs={"pk": imp.pk, "row_pk": row.pk},
        )
        in tresc
    )
    assert _url(imp, row) in tresc
    assert reverse("bpp:import-autor-autocomplete") in tresc
    assert "inny autor" in tresc
    assert 'name="imiona"' not in tresc


@pytest.mark.django_db
def test_partial_twardy_ma_zmien_autora(admin_client, admin_user):
    imp = _import(admin_user)
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(Autor, nazwisko="Zz", imiona="Aa")
    row = _row(
        imp,
        jednostka,
        autor=autor,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=True,
    )
    tresc = _results(admin_client, imp)
    assert _url(imp, row) in tresc
    assert "zmień autora" in tresc
    assert reverse("bpp:import-autor-autocomplete") in tresc
    assert 'name="imiona"' not in tresc
