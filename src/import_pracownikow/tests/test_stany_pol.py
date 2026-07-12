import pytest
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow


@pytest.mark.django_db
def test_stany_pol_jednostka_zmienione_zgodne_brak():
    jedn_stara = baker.make("bpp.Jednostka")
    jedn_nowa = baker.make("bpp.Jednostka")
    # aktualna_jednostka wprost (wzorzec conftest.py:140 / test_analyze_autoskip)
    autor = baker.make("bpp.Autor", aktualna_jednostka=jedn_stara)
    # zmienione: autor w innej jednostce niż docelowa
    row = baker.make(
        ImportPracownikowRow,
        autor=autor,
        jednostka=jedn_nowa,
        dane_znormalizowane={},
    )
    assert row.stany_pol()["jednostka"] == "zmienione"
    # brak: jednostka odroczona
    row2 = baker.make(
        ImportPracownikowRow,
        autor=autor,
        jednostka=None,
        dane_znormalizowane={},
    )
    assert row2.stany_pol()["jednostka"] == "brak"


@pytest.mark.django_db
def test_stany_pol_tytul_brak_bez_autora():
    # nazwa/skrót nie mogą kolidować z baseline (Tytul.nazwa="doktor" /
    # skrot="dr" już istnieją w baseline-sql/baseline.sql — UniqueViolation).
    dr = baker.make("bpp.Tytul", nazwa="doktor testowy 1", skrot="dr-t1")
    row = baker.make(
        ImportPracownikowRow,
        autor=None,
        tytul=dr,
        dane_znormalizowane={"tytuł_stopień": "dr"},
    )
    # niuans zatwierdzony: brak dopasowanego autora → "brak"
    assert row.stany_pol()["tytul"] == "brak"


@pytest.mark.django_db
def test_stany_pol_email_zgodne():
    autor = baker.make("bpp.Autor", email="a@x.pl")
    row = baker.make(
        ImportPracownikowRow,
        autor=autor,
        dane_znormalizowane={"email": "a@x.pl"},
    )
    assert row.stany_pol()["email"] == "zgodne"


@pytest.mark.django_db
def test_stany_pol_ma_wszystkie_klucze():
    row = baker.make(ImportPracownikowRow, autor=None, dane_znormalizowane={})
    assert set(row.stany_pol()) == {
        "jednostka",
        "email",
        "tytul",
        "stopien",
        "funkcja",
        "stanowisko",
    }


@pytest.mark.django_db
def test_stany_pol_snapshot_stabilny_po_integracji():
    """Po integracji baza = plik, ale snapshot pamięta że tytuł był zmieniony."""
    # literal nie-kolidujący z baseline.sql (unique skrot na Tytul)
    dr = baker.make("bpp.Tytul", nazwa="doktor testowy 2", skrot="dr-t2")
    jedn = baker.make("bpp.Jednostka")
    autor = baker.make("bpp.Autor", tytul=None)
    aj = baker.make("bpp.Autor_Jednostka", autor=autor, jednostka=jedn)
    row = baker.make(
        ImportPracownikowRow,
        autor=autor,
        autor_jednostka=aj,
        jednostka=jedn,
        tytul=dr,
        dane_znormalizowane={"tytuł_stopień": "dr"},
    )
    assert row.stany_pol()["tytul"] == "zmienione"  # live, pre-integracja
    row.zmiany_potrzebne = True
    row.integrate()
    row.refresh_from_db()
    # baza już zaktualizowana → live dałoby "zgodne", ale snapshot trzyma stan:
    assert row.stany_pol_snapshot is not None
    assert row.stany_pol()["tytul"] == "zmienione"


@pytest.mark.django_db
def test_stany_pol_jednostka_zmienione_gdy_autor_bez_aktualnej():
    """Spec: matched autor BEZ obecnej jednostki + jednostka docelowa =
    „zmienione" (integracja utworzy mu nowe AJ)."""
    jedn = baker.make("bpp.Jednostka")
    autor = baker.make("bpp.Autor", aktualna_jednostka=None)
    row = baker.make(
        ImportPracownikowRow, autor=autor, jednostka=jedn, dane_znormalizowane={}
    )
    assert row.stany_pol()["jednostka"] == "zmienione"


@pytest.mark.django_db
def test_stany_pol_funkcja_brak_bez_autor_jednostka():
    """Bez Autor_Jednostka funkcja = „brak" (nuans: nie ma z czym porównać)."""
    funkcja = baker.make("bpp.Funkcja_Autora")
    autor = baker.make("bpp.Autor")
    row = baker.make(
        ImportPracownikowRow,
        autor=autor,
        autor_jednostka=None,
        funkcja_autora=funkcja,
        dane_znormalizowane={"stanowisko": "adiunkt"},
    )
    assert row.stany_pol()["funkcja"] == "brak"


@pytest.mark.django_db
def test_integruj_wiersz_zamraza_snapshot_przed_materializacja():
    """Fix reviewera #1: snapshot zamrożony PRZED materializacją/integracją w
    pipeline — po integracji baza=plik (live dałoby „zgodne"), ale audytowy filtr
    pokazuje przedintegracyjny stan (tytuł „zmienione")."""
    from bpp.models import Autor_Jednostka
    from import_pracownikow.pipeline.integrate import _integruj_wiersz

    dr = baker.make("bpp.Tytul", nazwa="doktor testowy 9", skrot="dr-t9")
    jednostka = baker.make("bpp.Jednostka")
    autor = baker.make("bpp.Autor", nazwisko="Testowy", imiona="Pipeline", tytul=None)
    aj = baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka)
    imp = baker.make(ImportPracownikow)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        tytul=dr,
        dane_znormalizowane={"tytuł_stopień": "dr"},
        diff_do_utworzenia={},
        zmiany_potrzebne=True,
    )
    assert row.stany_pol()["tytul"] == "zmienione"  # pre-integracja
    _integruj_wiersz(row)
    row.refresh_from_db()
    assert row.stany_pol_snapshot is not None
    assert row.stany_pol()["tytul"] == "zmienione"  # snapshot trzyma stan
