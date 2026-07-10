import pytest
from model_bakery import baker

from bpp.models import (
    Autor,
    Jednostka,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)
from przemapuj_prace_autora import service
from przemapuj_prace_autora.models import PrzemapoaniePracAutora


@pytest.fixture
def autor():
    return baker.make(Autor, nazwisko="Kowalski", imiona="Jan")


@pytest.fixture
def jednostka_z():
    return baker.make(Jednostka, nazwa="Stara", skrot="ST")


@pytest.fixture
def jednostka_do():
    return baker.make(Jednostka, nazwa="Nowa", skrot="NW")


@pytest.mark.django_db
def test_przemapuj_przenosi_tylko_prace_ze_starej_jednostki(
    autor, jednostka_z, jednostka_do
):
    inna = baker.make(Jednostka, nazwa="Inna", skrot="IN")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Artykuł", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_z
    )
    # praca w innej jednostce — NIE ruszamy
    wc2 = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Inny", rok=2024)
    pa2 = baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc2, autor=autor, jednostka=inna)

    prz = service.przemapuj(autor, jednostka_z, jednostka_do, user=None)

    pa.refresh_from_db()
    pa2.refresh_from_db()
    assert pa.jednostka_id == jednostka_do.pk
    assert pa2.jednostka_id == inna.pk
    assert prz.liczba_prac_ciaglych == 1
    assert prz.liczba_prac_zwartych == 0


@pytest.mark.django_db
def test_przemapuj_buduje_wzbogacona_historie(autor, jednostka_z, jednostka_do):
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Art", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_z
    )
    wz = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Ksz", rok=2022)
    pz = baker.make(
        Wydawnictwo_Zwarte_Autor, rekord=wz, autor=autor, jednostka=jednostka_z
    )

    prz = service.przemapuj(autor, jednostka_z, jednostka_do, user=None)

    wpis_c = prz.prace_ciagle_historia[0]
    assert wpis_c["id"] == wc.id
    assert wpis_c["tytul"] == "Art"
    assert wpis_c["autor_rekord_pk"] == pa.pk
    assert wpis_c["jednostka_z_pk"] == jednostka_z.pk
    wpis_z = prz.prace_zwarte_historia[0]
    assert wpis_z["autor_rekord_pk"] == pz.pk
    assert wpis_z["jednostka_z_pk"] == jednostka_z.pk


@pytest.mark.django_db
def test_przemapuj_ustawia_zrodlowy_import(autor, jednostka_z, jednostka_do):
    from import_pracownikow.models import ImportPracownikow

    imp = baker.make(ImportPracownikow)
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="A", rok=2023)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_z)

    prz = service.przemapuj(
        autor, jednostka_z, jednostka_do, user=None, zrodlowy_import=imp
    )
    assert prz.zrodlowy_import_id == imp.pk
    assert PrzemapoaniePracAutora.objects.get(pk=prz.pk).zrodlowy_import_id == imp.pk
