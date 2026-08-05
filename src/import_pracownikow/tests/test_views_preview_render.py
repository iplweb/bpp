import pytest
from django.http import QueryDict
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
)
from import_pracownikow.pewnosc import STATUS_BRAK, STATUS_TWARDY, STATUS_WIELU


@pytest.mark.django_db
def test_podglad_pokazuje_badge_i_dropdown_kandydatow(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    a1 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_WIELU,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Jan", "nazwisko": "Kowalski"},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 7},
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=a1, pewnosc=1.0, powod="iexact"
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    tresc = resp.content.decode("utf-8")
    assert resp.status_code == 200
    # KONKRETNY badge statusu „wielu" (Foundation label alert + ikona +
    # etykieta) — nie samo „label"/„fi-", które przeciekają z base.html.
    # „wielu" jest czerwony (alert): wymaga uwagi operatora (poz. 6).
    assert "label alert" in tresc
    assert "fi-page-multiple" in tresc
    assert "wielu kandydatów" in tresc
    # dropdown kandydatów dla wielu (HTMX POST na wybierz-kandydata)
    assert (
        reverse(
            "import_pracownikow:wybierz-kandydata",
            kwargs={"pk": imp.pk, "row_pk": row.pk},
        )
        in tresc
    )
    # przycisk potwierdzenia kandydata: normalny (nie „tiny"), etykieta „potwierdź"
    assert "potwierdź" in tresc
    assert "button tiny" not in tresc


@pytest.mark.django_db
def test_podglad_sortuje_nie_twardy_na_gore(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(Autor, nazwisko="Zz", imiona="Aa")
    twardy = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=autor,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=True,
        dane_znormalizowane={},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 1},
    )
    wielu = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_WIELU,
        zmiany_potrzebne=False,
        dane_znormalizowane={},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 9},
    )
    from import_pracownikow.views import ImportPracownikowResultsView

    view = ImportPracownikowResultsView()
    view.kwargs = {"pk": imp.pk}
    # Widok filtruje w querysecie po parametrach GET, więc atrapa requestu
    # musi mieć QueryDict (pusty = brak filtrów).
    view.request = type("R", (), {"user": admin_user, "GET": QueryDict()})()
    lista = list(view.get_queryset())
    # non-twardy (wielu) mimo wyższego nr wiersza jest PRZED twardym
    assert lista[0].pk == wielu.pk
    assert lista[1].pk == twardy.pk


@pytest.mark.django_db
def test_podglad_pokazuje_jednostke_obecna_i_docelowa(admin_client, admin_user):
    """Kolumna „Jednostka": gdy autor jest już w innej jednostce niż z pliku,
    widok pokazuje OBECNĄ → DOCELOWĄ (regresja: wcześniej jednostek nie było
    widać wcale, więc operator nie wiedział skąd/dokąd przypina autora)."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    stara = baker.make(Jednostka, nazwa="Zaklad Obecny", skrot="ZO")
    nowa = baker.make(Jednostka, nazwa="Katedra Docelowa", skrot="KD")
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Jan")
    autor.dodaj_jednostke(stara)
    autor.refresh_from_db()
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=nowa,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=True,
        dane_znormalizowane={},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 0},
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    tresc = admin_client.get(url).content.decode("utf-8")
    assert "Jednostka (obecna → z pliku)" in tresc  # nagłówek nowej kolumny
    assert "Zaklad Obecny" in tresc  # obecna jednostka autora
    assert "Katedra Docelowa" in tresc  # docelowa z pliku
    assert "→ <strong>" in tresc  # forma „obecna → docelowa"


@pytest.mark.django_db
def test_podglad_ma_mostek_select2_change(admin_client, admin_user):
    """Regresja: zmiana autora przez Select2 nie zapisywała się, bo htmx słucha
    natywnego „change", a Select2 emituje go przez jQuery. Partial musi wystawiać
    mostek na select2:select/unselect → natywny dispatchEvent("change")."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_WIELU,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Jan", "nazwisko": "Kowalski"},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 1},
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    tresc = admin_client.get(url).content.decode("utf-8")
    assert "select2:select" in tresc
    assert "dispatchEvent(" in tresc


@pytest.mark.django_db
def test_podglad_wiersz_ma_atrybuty_data_diff(admin_client, admin_user):
    """Pierwszy <tr> rekordu niesie stan pól jako data-diff-* (zasila filtr)."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_WIELU,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Jan", "nazwisko": "Kowalski"},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 1},
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    tresc = admin_client.get(url).content.decode("utf-8")
    for klucz in (
        "jednostka",
        "email",
        "tytul",
        "stopien",
        "funkcja",
        "stanowisko",
        "data_od",
        "data_do",
    ):
        assert f"data-diff-{klucz}=" in tresc


@pytest.mark.django_db
def test_podglad_ma_pasek_filtrow_radia(admin_client, admin_user):
    """Pasek filtrów renderuje radia (wszystkie/zmienione/zgodne/brak) dla
    każdego z pól POLA_ROZNIC (w tym data_od/data_do). `mapowanie_kolumn`
    z kolumnami stopnia i stanowiska, żeby oba filtry (zwijane) się pojawiły."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
        mapowanie_kolumn={
            "S": "stopień_służbowy",
            "SD": "stanowisko_dydaktyczne",
        },
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    tresc = admin_client.get(url).content.decode("utf-8")
    assert 'id="filtr-roznic"' in tresc
    for klucz in (
        "jednostka",
        "email",
        "tytul",
        "stopien",
        "funkcja",
        "stanowisko",
        "data_od",
        "data_do",
    ):
        # Filtry idą teraz przez GET do querysetu (SQL), nie przez JS po DOM-ie.
        assert f'name="stan_{klucz}"' in tresc
    assert 'value="zmienione"' in tresc
    assert 'value="brak"' in tresc


@pytest.mark.django_db
def test_results_context_dzieli_pola_glowne_dodatkowe(admin_client, admin_user):
    """Widok dzieli POLA_ROZNIC na `pola_glowne` (zawsze widoczne: jednostka,
    tytuł, data od/do) i `pola_dodatkowe` (collapsible: email, stopień,
    funkcja, stanowisko)."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
        mapowanie_kolumn={
            "S": "stopień_służbowy",
            "SD": "stanowisko_dydaktyczne",
        },
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    ctx = admin_client.get(url).context
    assert [k for k, _, _ in ctx["pola_glowne"]] == [
        "jednostka",
        "tytul",
        "data_od",
        "data_do",
    ]
    assert [k for k, _, _ in ctx["pola_dodatkowe"]] == [
        "email",
        "stopien",
        "funkcja",
        "stanowisko",
    ]


@pytest.mark.django_db
def test_results_context_ukrywa_stopien_stanowisko_bez_kolumn(admin_client, admin_user):
    """Bez kolumny w pliku (`mapowanie_kolumn` puste) — stopień i stanowisko
    wypadają z `pola_dodatkowe` (nie filtrujemy po polu, którego nie ma)."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
        mapowanie_kolumn={},
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    ctx = admin_client.get(url).context
    assert [k for k, _, _ in ctx["pola_dodatkowe"]] == ["email", "funkcja"]
    assert [k for k, _, _ in ctx["pola_glowne"]] == [
        "jednostka",
        "tytul",
        "data_od",
        "data_do",
    ]


@pytest.mark.django_db
def test_karta_ukrywa_stopien_stanowisko_bez_kolumny(admin_client, admin_user):
    """Plik bez kolumny stopnia/stanowiska → karta NIE renderuje tych wierszy
    porównania (dane i tak by się nie zmieniły)."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
        mapowanie_kolumn={},
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Ewa")
    ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=autor,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Ewa", "nazwisko": "Nowak"},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 3},
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    tresc = admin_client.get(url).content.decode("utf-8")
    assert "Stopień sł.:" not in tresc
    assert "Stanowisko dyd.:" not in tresc
    # Pozostałe pola porównania zostają.
    assert "E-mail:" in tresc
    assert "Funkcja:" in tresc


@pytest.mark.django_db
def test_karta_pokazuje_stopien_stanowisko_z_kolumnami(admin_client, admin_user):
    """Plik z kolumnami stopnia/stanowiska → karta renderuje oba wiersze."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
        mapowanie_kolumn={
            "S": "stopień_służbowy",
            "SD": "stanowisko_dydaktyczne",
        },
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Ewa")
    ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=autor,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Ewa", "nazwisko": "Nowak"},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 3},
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    tresc = admin_client.get(url).content.decode("utf-8")
    assert "Stopień sł.:" in tresc
    assert "Stanowisko dyd.:" in tresc


@pytest.mark.django_db
def test_karta_zmien_autora_pod_autorem_i_etykieta_obecnie(admin_client, admin_user):
    """Kontrolka „zmień autora" przeniesiona do bloku akcji w komórce Autora;
    różnica e-maila renderuje etykietę „obecnie:" (dawniej „baza:")."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Ewa", email="stary@x.pl")
    ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=autor,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=False,
        dane_znormalizowane={
            "imię": "Ewa",
            "nazwisko": "Nowak",
            "email": "nowy@y.pl",
        },
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 3},
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    tresc = admin_client.get(url).content.decode("utf-8")
    assert "import-autor-akcje" in tresc
    assert "zmień autora" in tresc
    assert "obecnie:" in tresc
    assert "baza:" not in tresc


def _imp_przeanalizowany(admin_user, **kw):
    return baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
        **kw,
    )


@pytest.mark.django_db
def test_grid_pokazuje_wiersze_zatrudnienia_gdy_zmapowane(admin_client, admin_user):
    """Trzy wiersze zatrudnienia (wymiar/grupa/podstawowe) renderują się w
    karcie porównań, gdy odpowiednie kolumny są zmapowane."""
    imp = _imp_przeanalizowany(
        admin_user,
        mapowanie_kolumn={
            "Etat": "wymiar_etatu_tekst",
            "Grupa": "grupa_pracownicza",
            "Gł. zakład": "podstawowe_miejsce_pracy",
        },
    )
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Jan")
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    aj = baker.make(
        "bpp.Autor_Jednostka",
        autor=autor,
        jednostka=jednostka,
        wymiar_etatu=baker.make("bpp.Wymiar_Etatu"),
        grupa_pracownicza=baker.make("bpp.Grupa_Pracownicza"),
        podstawowe_miejsce_pracy=False,
    )
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=False,
        wymiar_etatu=baker.make("bpp.Wymiar_Etatu"),
        grupa_pracownicza=baker.make("bpp.Grupa_Pracownicza"),
        podstawowe_miejsce_pracy=True,
        dane_znormalizowane={"nazwisko": "Nowak", "imię": "Jan"},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 0},
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    tresc = admin_client.get(url).content.decode("utf-8")
    assert "Wymiar etatu:" in tresc
    assert "Grupa prac.:" in tresc
    assert "Podst. miejsce:" in tresc


@pytest.mark.django_db
def test_grid_ukrywa_wiersze_zatrudnienia_gdy_niezmapowane(admin_client, admin_user):
    imp = _imp_przeanalizowany(admin_user, mapowanie_kolumn={"E-mail": "email"})
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Jan")
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=False,
        dane_znormalizowane={"nazwisko": "Nowak", "imię": "Jan"},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 0},
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    tresc = admin_client.get(url).content.decode("utf-8")
    assert "Wymiar etatu:" not in tresc
    assert "Grupa prac.:" not in tresc
    assert "Podst. miejsce:" not in tresc


@pytest.mark.django_db
def test_brak_row_pokazuje_radio_pomin_utworz_dopasuj(admin_client, admin_user):
    """Wiersz „brak": jawny radio-wybór Pomiń / Utwórz / Dopasuj zamiast
    zakopanego linku + checkboxa."""
    imp = _imp_przeanalizowany(admin_user)
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=None,
        jednostka=jednostka,
        confidence=STATUS_BRAK,
        zmiany_potrzebne=False,
        dane_znormalizowane={"nazwisko": "Nowak", "imię": "Jan"},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 0},
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    tresc = admin_client.get(url).content.decode("utf-8")
    assert 'value="pomin"' in tresc
    assert 'value="utworz"' in tresc
    assert 'value="dopasuj"' in tresc
    assert "Pomiń — nie importuj" in tresc
    assert "Utwórz nowego autora" in tresc
    assert "Dopasuj do istniejącego" in tresc
