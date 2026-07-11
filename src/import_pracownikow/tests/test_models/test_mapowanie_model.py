import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from liveops.testing import MockProgress
from model_bakery import baker

from import_pracownikow.models import (
    AutorForm,
    ImportPracownikow,
    ImportPracownikowRow,
    JednostkaForm,
    ProfilMapowania,
)


@pytest.mark.django_db
def test_import_ma_pole_mapowanie_kolumn_domyslnie_puste():
    imp = baker.make(ImportPracownikow)
    assert imp.mapowanie_kolumn == {}


@pytest.mark.django_db
def test_stan_zmapowany_istnieje():
    assert ImportPracownikow.STAN_ZMAPOWANY == "zmapowany"
    kody = [k for k, _ in ImportPracownikow.STAN_CHOICES]
    assert "zmapowany" in kody


@pytest.mark.django_db
def test_profil_mapowania_zapis_i_odczyt(admin_user):
    p = ProfilMapowania.objects.create(
        nazwa="Uczelnia Vizja Q3",
        mapowanie={"jedn_org": "nazwa_jednostki", "nazwisko": "nazwisko"},
        utworzony_przez=admin_user,
    )
    p.refresh_from_db()
    assert p.mapowanie["jedn_org"] == "nazwa_jednostki"
    assert str(p) == "Uczelnia Vizja Q3"


def test_autorform_pola_nieidentyfikacyjne_opcjonalne():
    f = AutorForm()
    assert f.fields["nazwisko"].required is True
    assert f.fields["imię"].required is True
    for pole in [
        "stanowisko",
        "grupa_pracownicza",
        "data_zatrudnienia",
        "wymiar_etatu",
    ]:
        assert f.fields[pole].required is False, pole


def test_jednostkaform_wydzial_opcjonalny():
    f = JednostkaForm()
    assert f.fields["nazwa_jednostki"].required is True
    assert f.fields["wydział"].required is False


@pytest.mark.django_db
def test_naglowki_i_probka(admin_user):
    csv = (
        "Nazwisko;Imię;Nazwa jednostki\nKowalski;Jan;Katedra\nNowak;Ewa;Zakład\n"
    ).encode()
    imp = ImportPracownikow(owner=admin_user)
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()
    naglowki, probka = imp.naglowki_i_probka(limit=10)
    assert "nazwisko" in naglowki and "nazwa_jednostki" in naglowki
    assert "__xls_loc_row__" not in naglowki  # klucze lokalizacyjne odfiltrowane
    assert len(probka) == 2


@pytest.mark.django_db
def test_run_utworzony_nie_odpala_analizy(admin_user):
    # po Fazie 2: utworzony = czeka na mapowanie, run() jest no-op
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    imp.run(MockProgress(imp))  # nie może rzucić ani nic policzyć
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_UTWORZONY
    assert imp.importpracownikowrow_set.count() == 0


@pytest.mark.django_db
def test_on_restart_kasuje_wiersze_przy_zmapowany(admin_user):
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    baker.make("import_pracownikow.ImportPracownikowRow", parent=imp)
    imp.on_restart()
    assert imp.importpracownikowrow_set.count() == 0


@pytest.mark.django_db
def test_brak_stanowiska_nie_kasuje_funkcji_przy_integracji():
    # KRYTYCZNE: plik BEZ kolumny stanowisko (funkcja_autora=None na wierszu)
    # NIE może skasować istniejącej aj.funkcja na None podczas integracji.
    from bpp.models import Autor, Autor_Jednostka, Funkcja_Autora, Jednostka

    funkcja = baker.make(Funkcja_Autora)
    jednostka = baker.make(Jednostka)
    autor = baker.make(Autor)
    # podstawowe_miejsce_pracy=True izoluje test od #4 (domyślnie import ustawia
    # jednostkę autora jako podstawowe miejsce pracy); tu sprawdzamy tylko, że
    # brak stanowiska w pliku nie kasuje istniejącej funkcji.
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        funkcja=funkcja,
        podstawowe_miejsce_pracy=True,
    )
    row = baker.make(
        ImportPracownikowRow,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        funkcja_autora=None,  # brak stanowiska w pliku
        grupa_pracownicza=None,
        wymiar_etatu=None,
        podstawowe_miejsce_pracy=None,
        dane_znormalizowane={},
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    # ani check, ani integracja nie ruszają funkcji gdy wiersz jej nie ma
    dane = row.dane_bardziej_znormalizowane
    assert row._check_autor_jednostka_needs_update(dane) is False
    row._integrate_autor_jednostka()
    aj.refresh_from_db()
    assert aj.funkcja_id == funkcja.pk  # NIE skasowane
