import pytest
from model_bakery import baker

from import_pracownikow.models import ImportPracownikowRow


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
