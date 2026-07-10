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


@pytest.mark.django_db
def test_cofnij_przywraca_prace(autor, jednostka_z, jednostka_do):
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="A", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_z
    )
    prz = service.przemapuj(autor, jednostka_z, jednostka_do, user=None)
    pa.refresh_from_db()
    assert pa.jednostka_id == jednostka_do.pk

    cofnieto, pominieto = service.cofnij(prz)

    pa.refresh_from_db()
    assert pa.jednostka_id == jednostka_z.pk
    assert (cofnieto, pominieto) == (1, 0)


@pytest.mark.django_db
def test_cofnij_guard_praca_zmienila_jednostke_po(autor, jednostka_z, jednostka_do):
    trzecia = baker.make(Jednostka, nazwa="Trzecia", skrot="TR")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="A", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_z
    )
    prz = service.przemapuj(autor, jednostka_z, jednostka_do, user=None)
    # praca po przemapowaniu zmieniła afiliację ręcznie — NIE cofamy na ślepo
    Wydawnictwo_Ciagle_Autor.objects.filter(pk=pa.pk).update(jednostka=trzecia)

    cofnieto, pominieto = service.cofnij(prz)

    pa.refresh_from_db()
    assert pa.jednostka_id == trzecia.pk
    assert (cofnieto, pominieto) == (0, 1)


@pytest.mark.django_db
def test_cofnij_pomija_stary_wpis_bez_autor_rekord_pk(autor, jednostka_z, jednostka_do):
    prz = PrzemapoaniePracAutora.objects.create(
        autor=autor,
        jednostka_z=jednostka_z,
        jednostka_do=jednostka_do,
        prace_ciagle_historia=[{"id": 1, "tytul": "stary", "rok": 2020}],
        prace_zwarte_historia=[],
    )
    cofnieto, pominieto = service.cofnij(prz)
    assert (cofnieto, pominieto) == (0, 1)


@pytest.mark.django_db
def test_cofnij_pomija_wpis_ze_skasowana_jednostka_z(autor, jednostka_z, jednostka_do):
    # F6: jednostka źródłowa undo usunięta w międzyczasie — wpis pomijamy
    # (bez próby save → bez IntegrityError wywracającego CAŁE undo).
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="A", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_do
    )
    prz = PrzemapoaniePracAutora.objects.create(
        autor=autor,
        jednostka_z=jednostka_z,
        jednostka_do=jednostka_do,
        prace_ciagle_historia=[
            {
                "id": wc.id,
                "tytul": "A",
                "rok": 2023,
                "autor_rekord_pk": pa.pk,
                "jednostka_z_pk": 987654321,
            }
        ],
        prace_zwarte_historia=[],
    )

    cofnieto, pominieto = service.cofnij(prz)

    pa.refresh_from_db()
    assert pa.jednostka_id == jednostka_do.pk  # NIETKNIĘTE
    assert (cofnieto, pominieto) == (0, 1)


@pytest.mark.django_db
def test_cofnij_idempotentne(autor, jednostka_z, jednostka_do):
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="A", rok=2023)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_z)
    prz = service.przemapuj(autor, jednostka_z, jednostka_do, user=None)

    assert service.cofnij(prz) == (1, 0)
    # drugie cofnięcie: praca już w jednostka_z != jednostka_do → pominięta
    assert service.cofnij(prz) == (0, 1)
    # rekord audytu NIE skasowany
    assert PrzemapoaniePracAutora.objects.filter(pk=prz.pk).exists()


@pytest.mark.django_db
def test_cofnij_omija_clean_dyscypliny(autor, jednostka_z, jednostka_do):
    # G1: praca z `dyscyplina_naukowa`, dla której autor NIE ma
    # `Autor_Dyscyplina` na rok rekordu → `obj.save()` odpaliłby
    # `clean()`/`_waliduj_dyscypline` (ValidationError). Querysetowy `.update()`
    # w `cofnij` (symetryczny z forward `przemapuj`) omija clean/side-effecty →
    # undo przechodzi. Stan budujemy przez `.update()`, by NIE odpalić clean
    # przy tworzeniu (baker.make woła save()).
    from bpp.models import Dyscyplina_Naukowa

    dyscyplina = baker.make(Dyscyplina_Naukowa)
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="A", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_z
    )
    Wydawnictwo_Ciagle_Autor.objects.filter(pk=pa.pk).update(
        dyscyplina_naukowa=dyscyplina
    )
    prz = service.przemapuj(autor, jednostka_z, jednostka_do, user=None)
    pa.refresh_from_db()
    assert pa.jednostka_id == jednostka_do.pk

    cofnieto, pominieto = service.cofnij(prz)

    pa.refresh_from_db()
    assert pa.jednostka_id == jednostka_z.pk
    assert (cofnieto, pominieto) == (1, 0)
