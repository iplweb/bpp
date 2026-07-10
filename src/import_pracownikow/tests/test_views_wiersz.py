import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
)
from import_pracownikow.pewnosc import STATUS_TWARDY, STATUS_WIELU


def _wielu_row(owner):
    imp = baker.make(
        ImportPracownikow, owner=owner, stan=ImportPracownikow.STAN_PRZEANALIZOWANY
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    a1 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    a2 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_WIELU,
        zmiany_potrzebne=False,
        dane_znormalizowane={},
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=a1, pewnosc=1.0, powod="iexact"
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=a2, pewnosc=1.0, powod="iexact"
    )
    return imp, row, a1


@pytest.mark.django_db
def test_wybor_kandydata_materializuje_autora(admin_client, admin_user):
    imp, row, a1 = _wielu_row(admin_user)
    url = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"wybrany_kandydat": a1.pk})
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.wybrany_kandydat_id == a1.pk
    assert row.autor_id == a1.pk
    assert row.confidence == STATUS_TWARDY
    assert row.zmiany_potrzebne is True


@pytest.mark.django_db
def test_wybor_kandydata_odrzuca_obcego_autora(admin_client, admin_user):
    imp, row, a1 = _wielu_row(admin_user)
    obcy = baker.make(Autor, nazwisko="Obcy", imiona="Ktoś")
    url = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"wybrany_kandydat": obcy.pk})
    assert resp.status_code == 400
    row.refresh_from_db()
    assert row.autor is None


@pytest.mark.django_db
def test_wybor_kandydata_owner_scoped(client, django_user_model, admin_user):
    imp, row, a1 = _wielu_row(admin_user)
    inny = django_user_model.objects.create_user(
        username="inny", password="x", is_staff=True
    )
    from django.contrib.auth.models import Group

    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    inny.groups.add(grupa)
    client.force_login(inny)
    url = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = client.post(url, {"wybrany_kandydat": a1.pk})
    assert resp.status_code == 404


@pytest.mark.django_db
def test_wybor_kandydata_odrzucony_gdy_import_zintegrowany(admin_client, admin_user):
    # G3: bramka stanu — POST wyboru na wierszu importu już zintegrowanego
    # (retry HTMX / back-button / wyścig z Zatwierdź) MUSI dać 400 i NIE
    # nadpisać danych po commicie ani integrować drugi raz.
    imp, row, a1 = _wielu_row(admin_user)
    imp.stan = ImportPracownikow.STAN_ZINTEGROWANY
    imp.save(update_fields=["stan"])
    url = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"wybrany_kandydat": a1.pk})
    assert resp.status_code == 400
    row.refresh_from_db()
    assert row.autor is None


@pytest.mark.django_db
def test_odtworz_autor_jednostka_zdejmuje_wpis_i_odklada_create():
    # G1 (jednostkowy): stary diff AJ dla POPRZEDNIEGO autora zostaje zdjęty,
    # a dla nowego autora BEZ istniejącego AJ odkładany jest świeży create.
    from bpp.models import Autor, Jednostka
    from import_pracownikow.pewnosc import odtworz_autor_jednostka

    imp = baker.make(ImportPracownikow)
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    stary = baker.make(Autor, nazwisko="Stary", imiona="Jan")
    nowy = baker.make(Autor, nazwisko="Nowy", imiona="Jan")  # bez AJ
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=nowy,
        zmiany_potrzebne=True,
        dane_znormalizowane={},
        diff_do_utworzenia={
            "autor_jednostka": {"autor": stary.pk, "jednostka": jednostka.pk}
        },
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    odtworz_autor_jednostka(row, nowy)
    assert row.autor_jednostka is None
    assert row.diff_do_utworzenia["autor_jednostka"]["autor"] == nowy.pk
    assert row.zmiany_potrzebne is True


@pytest.mark.django_db
def test_wybor_kandydata_nie_koruptuje_aj_starego_autora(admin_client, admin_user):
    # G1 (regresja korupcji): wiersz miał odłożony diff AJ dla STAREGO autora
    # (np. z wcześniejszej ścieżki analizy), a user wybiera NOWEGO kandydata,
    # który MA już Autor_Jednostka. Po wyborze uśpiony wpis starego autora musi
    # zniknąć — inaczej integracja utworzyłaby AJ dla starego i nadpisała
    # row.autor_jednostka (dane zatrudnienia nowego autora u starego).
    from bpp.models import Autor, Autor_Jednostka, Jednostka

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    stary = baker.make(Autor, nazwisko="Stary", imiona="Jan")
    nowy = baker.make(Autor, nazwisko="Nowy", imiona="Jan")
    aj_nowy = baker.make(Autor_Jednostka, autor=nowy, jednostka=jednostka)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_WIELU,
        zmiany_potrzebne=False,
        dane_znormalizowane={},
        diff_do_utworzenia={
            "autor_jednostka": {"autor": stary.pk, "jednostka": jednostka.pk}
        },
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=stary, pewnosc=1.0, powod="iexact"
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=nowy, pewnosc=1.0, powod="iexact"
    )
    url = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"wybrany_kandydat": nowy.pk})
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.autor_id == nowy.pk
    assert "autor_jednostka" not in row.diff_do_utworzenia
    assert row.autor_jednostka_id == aj_nowy.pk
    # stary autor nie dostał żadnego AJ (nie było i nie powstało)
    assert not Autor_Jednostka.objects.filter(autor=stary).exists()


from import_pracownikow.pewnosc import STATUS_BRAK  # noqa: E402


@pytest.mark.django_db
def test_edycja_inline_rematchuje_i_zapisuje_korekte(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow, owner=admin_user, stan=ImportPracownikow.STAN_PRZEANALIZOWANY
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    # w bazie jest właściwy autor, ale wiersz startowo „brak" (błędne rozbicie)
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_BRAK,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Janx", "nazwisko": "Kowalskix"},
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    url = reverse(
        "import_pracownikow:edytuj-wiersz",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(
        url, {"imiona": "Jan", "nazwisko": "Kowalski", "tytul": ""}
    )
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.korekta_uzytkownika["nazwisko"] == "Kowalski"
    assert row.autor_id == autor.pk
    assert row.confidence == STATUS_TWARDY
    assert row.dane_znormalizowane["nazwisko"] == "Kowalski"


@pytest.mark.django_db
def test_edycja_inline_korekta_tytulu_ustawia_fk(admin_client, admin_user):
    # F6: korekta tytułu musi zaktualizować FK row.tytul (integracja czyta
    # row.tytul_id, nie JSON) — inaczej do bazy trafi stary tytuł.
    from bpp.models import Tytul

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    # Tytul.skrot/nazwa unique + baseline preloaduje „dr" → get_or_create.
    tytul = Tytul.objects.get_or_create(skrot="dr", defaults={"nazwa": "doktor"})[0]
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        tytul=None,
        confidence=STATUS_BRAK,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Jan", "nazwisko": "Kowalski"},
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    url = reverse(
        "import_pracownikow:edytuj-wiersz",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(
        url, {"imiona": "Jan", "nazwisko": "Kowalski", "tytul": "dr"}
    )
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.tytul_id == tytul.pk
    assert row.dane_znormalizowane["tytuł_stopień"] == "dr"


@pytest.mark.django_db
def test_edycja_inline_brak_zdejmuje_uspiony_wpis_aj(admin_client, admin_user):
    # G1 (ścieżka autor=None): wiersz miał odłożony diff AJ dla starego autora,
    # a korekta prowadzi do statusu „brak" (re-match nie znajduje nikogo) →
    # uśpiony wpis AJ MUSI zniknąć, inaczej integracja utworzyłaby AJ dla
    # już-nie-autora wiersza.
    from bpp.models import Autor, Jednostka

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    stary = baker.make(Autor, nazwisko="Stary", imiona="Jan")
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=stary,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=True,
        dane_znormalizowane={"imię": "Jan", "nazwisko": "Stary"},
        diff_do_utworzenia={
            "autor_jednostka": {"autor": stary.pk, "jednostka": jednostka.pk}
        },
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    url = reverse(
        "import_pracownikow:edytuj-wiersz",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(
        url, {"imiona": "Zdzisław", "nazwisko": "Nieistniejacy", "tytul": ""}
    )
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.autor is None
    assert row.confidence == STATUS_BRAK
    assert "autor_jednostka" not in row.diff_do_utworzenia
    assert row.autor_jednostka is None
    assert row.zmiany_potrzebne is False


@pytest.mark.django_db
def test_edycja_inline_odrzucona_gdy_import_zintegrowany(admin_client, admin_user):
    # G3: bramka stanu — POST korekty na wierszu importu już zintegrowanego
    # MUSI dać 400 i NIE zmutować wiersza (audyt log_zmian po commicie).
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZINTEGROWANY,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_BRAK,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Janx", "nazwisko": "Kowalskix"},
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    url = reverse(
        "import_pracownikow:edytuj-wiersz",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(
        url, {"imiona": "Jan", "nazwisko": "Kowalski", "tytul": ""}
    )
    assert resp.status_code == 400
    row.refresh_from_db()
    assert row.autor is None
    assert row.confidence == STATUS_BRAK
    assert row.korekta_uzytkownika == {}


@pytest.mark.django_db
def test_edycja_inline_owner_scoped(client, django_user_model, admin_user):
    imp = baker.make(
        ImportPracownikow, owner=admin_user, stan=ImportPracownikow.STAN_PRZEANALIZOWANY
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_BRAK,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Jan", "nazwisko": "Kowalski"},
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    inny = django_user_model.objects.create_user(
        username="inny", password="x", is_staff=True
    )
    from django.contrib.auth.models import Group

    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    inny.groups.add(grupa)
    client.force_login(inny)
    url = reverse(
        "import_pracownikow:edytuj-wiersz",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = client.post(url, {"imiona": "Jan", "nazwisko": "Kowalski", "tytul": ""})
    assert resp.status_code == 404
